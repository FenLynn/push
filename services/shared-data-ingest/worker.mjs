// Standalone module Worker maintained with the upload client in the Push repo.
// Paste this entire file into Cloudflare's code editor.
// No build tools, dependencies, deployment CLI, D1, or Cloudflare API token.
const VERSION = '1.0.4';
const MAX_BODY_BYTES = 1024 * 1024;
const JWKS_TTL_MS = 60 * 60 * 1000;
const JWKS_REFRESH_INTERVAL_MS = 60 * 1000;
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true });
const MODULE_ID = /^[a-z0-9][a-z0-9_-]*:[a-z0-9][a-z0-9_-]*$/;
const KEY_NAME = /^[a-z0-9][a-z0-9:_-]{1,200}$/;
const DEFAULT_REGISTRY = {
  'push:smoke': { key: 'v1:push:smoke:latest', repository: 'FenLynn/push', expirationTtl: 86400 },
};

class HttpError extends Error {
  constructor(status, code, message, authReason, authInfo) {
    super(message);
    this.status = status;
    this.code = code;
    this.authReason = authReason;
    this.authInfo = authInfo;
  }
}

function json(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
    },
  });
}

function fail(status, code, message) {
  throw new HttpError(status, code, message);
}

// Call only with fixed reason codes, never values from a JWT or configuration.
function rejectAccess(reason, authInfo) {
  throw new HttpError(403, 'invalid_access_token', 'Access token validation failed.', reason, authInfo);
}

async function audienceDiagnostics(audience, configuredAudience) {
  const sha256 = async value => Array.from(new Uint8Array(
    await crypto.subtle.digest('SHA-256', encoder.encode(value)),
  ), byte => byte.toString(16).padStart(2, '0')).join('');
  const values = typeof audience === 'string' ? [audience] : Array.isArray(audience) ? audience : [];
  // Called only after signature verification. Hash only public, well-formed
  // Access application IDs; never echo an assertion, identity or raw claim.
  const ids = values.filter(value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)).slice(0, 8);
  return {
    audienceShape: typeof audience === 'string' ? 'string' : Array.isArray(audience) ? 'array'
      : audience === undefined ? 'missing' : 'other',
    configuredAudienceSha256: await sha256(configuredAudience),
    tokenAudienceSha256: await Promise.all(ids.map(sha256)),
  };
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function decodeBase64Url(value) {
  if (!value || !/^[A-Za-z0-9_-]+$/.test(value)) fail(403, 'invalid_access_token', 'Invalid Access token.');
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(base64 + '='.repeat((4 - base64.length % 4) % 4));
  return Uint8Array.from(binary, character => character.charCodeAt(0));
}

function parsePart(value) {
  const parsed = JSON.parse(decoder.decode(decodeBase64Url(value)));
  if (!isObject(parsed)) fail(403, 'invalid_access_token', 'Invalid Access token.');
  return parsed;
}

function getConfiguration(env) {
  const teamDomain = String(env.TEAM_DOMAIN || '').trim();
  let issuer;
  try {
    const url = new URL(teamDomain);
    if (url.protocol !== 'https:' || !/^[a-z0-9-]+\.cloudflareaccess\.com$/.test(url.hostname)
      || url.port || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error();
    issuer = url.origin;
  } catch {
    fail(503, 'configuration_error', 'Configure TEAM_DOMAIN as an HTTPS Cloudflare Access team domain.');
  }
  const audience = String(env.POLICY_AUD || '').trim();
  if (!/^[a-f0-9]{64}$/.test(audience)) fail(503, 'configuration_error', 'Configure the application POLICY_AUD.');
  const hostname = String(env.INGEST_HOSTNAME || '').trim().toLowerCase();
  if (!/^[a-z0-9.-]+$/.test(hostname)) fail(503, 'configuration_error', 'Invalid INGEST_HOSTNAME.');
  return { issuer, audience, hostname, clientId: String(env.ACCESS_CLIENT_ID || '').trim() };
}

function getRegistry(env) {
  let registry;
  try {
    registry = env.MODULE_REGISTRY_JSON ? JSON.parse(env.MODULE_REGISTRY_JSON) : DEFAULT_REGISTRY;
  } catch {
    fail(503, 'configuration_error', 'MODULE_REGISTRY_JSON must be valid JSON.');
  }
  const entries = isObject(registry) ? Object.entries(registry) : [];
  if (!entries.length || entries.length > 64) fail(503, 'configuration_error', 'Invalid module registry.');
  const keys = new Set();
  for (const [id, entry] of entries) {
    if (!MODULE_ID.test(id) || id.length > 100 || !isObject(entry) || typeof entry.key !== 'string'
      || !KEY_NAME.test(entry.key) || keys.has(entry.key)
      || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(entry.repository || '')
      || (entry.expirationTtl !== undefined && (!Number.isInteger(entry.expirationTtl) || entry.expirationTtl < 60))) {
      fail(503, 'configuration_error', 'Invalid module registry entry.');
    }
    keys.add(entry.key);
  }
  return new Map(entries);
}

async function boundedText(body, maxBytes) {
  if (!body) return '';
  const reader = body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        fail(413, 'payload_too_large', 'Request exceeds the size limit.');
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return decoder.decode(bytes);
}

async function readEnvelope(request) {
  if (request.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase() !== 'application/json') {
    fail(415, 'unsupported_media_type', 'Use Content-Type: application/json.');
  }
  const length = request.headers.get('Content-Length');
  if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_BODY_BYTES)) {
    fail(413, 'payload_too_large', 'Request exceeds the 1 MiB size limit.');
  }
  try {
    const envelope = JSON.parse(await boundedText(request.body, MAX_BODY_BYTES));
    if (!isObject(envelope)) fail(400, 'invalid_snapshot', 'Upload a snapshot object.');
    return envelope;
  } catch (error) {
    if (error instanceof HttpError) throw error;
    fail(400, 'invalid_json', 'Request must contain valid UTF-8 JSON.');
  }
}

function validateEnvelope(envelope, registry, nowMs) {
  const allowedFields = new Set(['schemaVersion', 'module', 'generatedAt', 'source', 'payload']);
  if (Object.keys(envelope).some(key => !allowedFields.has(key)) || envelope.schemaVersion !== 1) {
    fail(400, 'invalid_snapshot', 'Unknown fields or unsupported schemaVersion.');
  }
  const entry = registry.get(envelope.module);
  if (!entry) fail(400, 'unknown_module', 'Module is not registered.');
  const generatedAt = envelope.generatedAt;
  const timestamp = typeof generatedAt === 'string' ? Date.parse(generatedAt) : NaN;
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(generatedAt || '')
    || !Number.isFinite(timestamp) || timestamp > nowMs + 5 * 60 * 1000
    || new Date(timestamp).toISOString() !== generatedAt.replace(/Z$/, generatedAt.includes('.') ? 'Z' : '.000Z')) {
    fail(400, 'invalid_timestamp', 'generatedAt must be a valid UTC ISO timestamp, not in the future.');
  }
  if ((!isObject(envelope.payload) && !Array.isArray(envelope.payload)) || !Object.keys(envelope.payload).length) {
    fail(400, 'empty_payload', 'A non-empty object or array payload is required.');
  }
  const source = envelope.source;
  if (!isObject(source) || source.repository !== entry.repository) {
    fail(400, 'invalid_source', 'source.repository must match the module registry.');
  }
  const sourceFields = new Set(['repository', 'commit', 'runId', 'runNumber', 'runAttempt']);
  if (Object.keys(source).some(key => !sourceFields.has(key))
    || (source.commit !== undefined && !/^[a-f0-9]{40}$/.test(source.commit))
    || ['runId', 'runNumber', 'runAttempt'].some(field => source[field] !== undefined
      && (typeof source[field] !== 'string' || !/^\d{1,32}$/.test(source[field])))) {
    fail(400, 'invalid_source', 'Invalid source metadata.');
  }
  return entry;
}

export function createIngestWorker({ fetcher = (...args) => fetch(...args), now = () => Date.now() } = {}) {
  // In-memory caching only. Authentication never reads/writes KV or D1.
  const keyCaches = new Map();

  async function getVerificationKey(issuer, kid) {
    let cache = keyCaches.get(issuer);
    if (!cache) {
      cache = { keys: new Map(), loadedAt: -Infinity, attemptedAt: -Infinity, pending: null };
      keyCaches.set(issuer, cache);
    }
    let currentTime = now();
    if (cache.keys.has(kid) && currentTime - cache.loadedAt < JWKS_TTL_MS) return cache.keys.get(kid);
    if (!cache.pending && currentTime - cache.attemptedAt >= JWKS_REFRESH_INTERVAL_MS) {
      cache.attemptedAt = currentTime;
      cache.pending = (async () => {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 5000);
        try {
          const response = await fetcher(`${issuer}/cdn-cgi/access/certs`, {
            // workerd rejects redirect:"error" at Request construction. Use
            // manual and reject every non-2xx response (including all 3xx).
            headers: { Accept: 'application/json' }, redirect: 'manual', signal: controller.signal,
          });
          if (!response.ok) throw new Error();
          const document = JSON.parse(await boundedText(response.body, 128 * 1024));
          if (!Array.isArray(document.keys) || !document.keys.length || document.keys.length > 32) throw new Error();
          const keys = new Map();
          for (const jwk of document.keys) {
            if (jwk.kty !== 'RSA' || typeof jwk.kid !== 'string' || jwk.kid.length > 128
              || (jwk.alg && jwk.alg !== 'RS256') || (jwk.use && jwk.use !== 'sig')) continue;
            const key = await crypto.subtle.importKey('jwk', jwk,
              { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
            keys.set(jwk.kid, key);
          }
          if (!keys.size) throw new Error();
          cache.keys = keys;
          cache.loadedAt = now();
        } catch {
          fail(503, 'access_keys_unavailable', 'Access verification keys are temporarily unavailable.');
        } finally {
          clearTimeout(timer);
        }
      })().finally(() => { cache.pending = null; });
    }
    if (cache.pending) await cache.pending;
    currentTime = now();
    if (currentTime - cache.loadedAt >= JWKS_TTL_MS) {
      fail(503, 'access_keys_unavailable', 'Access verification keys are temporarily unavailable.');
    }
    const key = cache.keys.get(kid);
    if (!key) rejectAccess('unknown_signing_key');
    return key;
  }

  async function authenticate(request, configuration) {
    const token = request.headers.get('Cf-Access-Jwt-Assertion');
    if (!token) fail(401, 'access_required', 'Cloudflare Access service authentication is required.');
    if (token.length > 8192) rejectAccess('token_too_large');
    let header, claims, parts, signature;
    try {
      parts = token.split('.');
      if (parts.length !== 3) throw new Error();
      header = parsePart(parts[0]);
      claims = parsePart(parts[1]);
      signature = decodeBase64Url(parts[2]);
    } catch {
      rejectAccess('malformed_token');
    }
    const seconds = Math.floor(now() / 1000);
    if (header.alg !== 'RS256' || typeof header.kid !== 'string' || !header.kid || header.kid.length > 128
      || (header.typ !== undefined && header.typ !== 'JWT') || header.crit !== undefined) rejectAccess('unsupported_header');
    if (claims.iss !== configuration.issuer) rejectAccess('issuer_mismatch');
    if (claims.type !== 'app') rejectAccess('token_type_mismatch');
    if (!Number.isInteger(claims.exp) || !Number.isInteger(claims.iat) || claims.iat >= claims.exp
      || (claims.nbf !== undefined && !Number.isInteger(claims.nbf))) rejectAccess('invalid_token_time');
    if (claims.exp <= seconds) rejectAccess('expired_token');
    if (claims.iat > seconds + 30 || (claims.nbf !== undefined && claims.nbf > seconds)) rejectAccess('token_not_yet_valid');
    if (claims.sub !== '' || typeof claims.common_name !== 'string'
      || !/^[A-Za-z0-9_-]+\.access$/.test(claims.common_name)) rejectAccess('service_identity_mismatch');
    if (configuration.clientId && claims.common_name !== configuration.clientId) rejectAccess('client_id_mismatch');
    const key = await getVerificationKey(configuration.issuer, header.kid);
    if (!await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, signature, encoder.encode(`${parts[0]}.${parts[1]}`))) {
      rejectAccess('signature_mismatch');
    }
    // RFC 7519 section 4.1.3 permits either a single string or an array of
    // strings. This is exact membership, never substring or prefix matching.
    const audiences = typeof claims.aud === 'string' ? [claims.aud] : claims.aud;
    if (!Array.isArray(audiences) || !audiences.length || audiences.some(value => typeof value !== 'string')) {
      rejectAccess('invalid_audience_format', await audienceDiagnostics(claims.aud, configuration.audience));
    }
    if (!audiences.includes(configuration.audience)) {
      rejectAccess('audience_mismatch', await audienceDiagnostics(claims.aud, configuration.audience));
    }
  }

  return {
    async fetch(request, env) {
      try {
        const configuration = getConfiguration(env);
        const url = new URL(request.url);
        if (url.protocol !== 'https:' || url.hostname !== configuration.hostname || url.port) {
          fail(403, 'hostname_not_allowed', 'Use the protected ingest hostname.');
        }
        await authenticate(request, configuration);
        if (!env.SHARED_DATA_KV || typeof env.SHARED_DATA_KV.get !== 'function' || typeof env.SHARED_DATA_KV.put !== 'function') {
          fail(503, 'configuration_error', 'Bind the dedicated SHARED_DATA_KV namespace.');
        }
        if (url.pathname === '/api/health') {
          if (request.method !== 'GET') fail(405, 'method_not_allowed', 'Use GET.');
          return json({ success: true, service: 'shared-data-ingest', version: VERSION });
        }
        if (url.pathname !== '/api/ingest' && url.pathname !== '/api/status') fail(404, 'not_found', 'Unknown endpoint.');
        const registry = getRegistry(env);
        if (url.pathname === '/api/status') {
          if (request.method !== 'GET') fail(405, 'method_not_allowed', 'Use GET.');
          const module = url.searchParams.get('module');
          const entry = registry.get(module);
          if (!entry) fail(400, 'unknown_module', 'Module is not registered.');
          let raw;
          try { raw = await env.SHARED_DATA_KV.get(entry.key); }
          catch { fail(503, 'kv_unavailable', 'KV read is temporarily unavailable.'); }
          if (raw === null) fail(404, 'snapshot_not_found', 'No snapshot has been published yet.');
          let snapshot;
          try { snapshot = JSON.parse(raw); }
          catch { fail(502, 'invalid_stored_snapshot', 'Stored snapshot is not valid JSON.'); }
          return json({ success: true, module, key: entry.key, snapshot });
        }
        if (request.method !== 'POST') fail(405, 'method_not_allowed', 'Use POST.');
        const envelope = await readEnvelope(request);
        const entry = validateEnvelope(envelope, registry, now());
        const snapshot = { ...envelope, receivedAt: new Date(now()).toISOString() };
        const options = entry.expirationTtl ? { expirationTtl: entry.expirationTtl } : {};
        try { await env.SHARED_DATA_KV.put(entry.key, JSON.stringify(snapshot), options); }
        catch { fail(503, 'kv_unavailable', 'KV write is temporarily unavailable; retry after a delay.'); }
        return json({ success: true, module: envelope.module, key: entry.key, receivedAt: snapshot.receivedAt });
      } catch (error) {
        if (error instanceof HttpError) return json({
          success: false, error: error.code, message: error.message,
          ...(error.authReason ? { authReason: error.authReason } : {}),
          ...(error.authInfo ? { authInfo: error.authInfo } : {}),
        }, error.status);
        return json({ success: false, error: 'internal_error', message: 'The request could not be completed.' }, 500);
      }
    },
  };
}

export default createIngestWorker();
