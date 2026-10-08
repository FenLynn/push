// Invoke with the standalone workerd binary's `test` command, never a deployment CLI.
// All assertions use generated local keys and an in-memory fetch/KV fixture.
import { createIngestWorker } from './worker.mjs';

const AUD = 'a'.repeat(64);
const ISSUER = 'https://unit-test.cloudflareaccess.com';
const CLIENT_ID = 'runtime-test.access';
const NOW = Date.parse('2026-10-08T03:00:00.000Z');
const encoder = new TextEncoder();
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const base64url = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const part = value => base64url(encoder.encode(JSON.stringify(value)));

async function fixture(status = 200) {
  const pair = await crypto.subtle.generateKey({
    name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048,
    publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256',
  }, true, ['sign', 'verify']);
  const publicKey = { ...await crypto.subtle.exportKey('jwk', pair.publicKey), kid: 'current', alg: 'RS256', use: 'sig' };
  const calls = { jwks: 0, reads: 0, writes: 0 };
  const worker = createIngestWorker({
    now: () => NOW,
    fetcher: async (url, init) => {
      calls.jwks++;
      // This native constructor catches Node/Workers RequestInit differences.
      const native = new Request(url, init);
      assert(native.url === `${ISSUER}/cdn-cgi/access/certs`, 'JWKS host changed');
      assert(native.redirect === 'manual', 'JWKS must not automatically follow redirects');
      assert(!native.headers.has('Cf-Access-Client-Secret') && !native.headers.has('Cf-Access-Jwt-Assertion'), 'Credential forwarded');
      return new Response(JSON.stringify({ keys: [publicKey] }), { status });
    },
  });
  const env = {
    TEAM_DOMAIN: ISSUER, POLICY_AUD: AUD, ACCESS_CLIENT_ID: CLIENT_ID,
    SHARED_DATA_KV: {
      async get() { calls.reads++; return null; },
      async put() { calls.writes++; },
    },
  };
  async function health(aud = [AUD], forged = false) {
    const header = part({ alg: 'RS256', kid: 'current', typ: 'JWT' });
    const claims = part({ type: 'app', iss: ISSUER, aud, sub: '', common_name: CLIENT_ID,
      iat: NOW / 1000 - 10, exp: NOW / 1000 + 300 });
    const signature = forged ? new Uint8Array(256) : new Uint8Array(await crypto.subtle.sign(
      'RSASSA-PKCS1-v1_5', pair.privateKey, encoder.encode(`${header}.${claims}`),
    ));
    return worker.fetch(new Request('https://ingest.660415.xyz/api/health', {
      headers: { 'Cf-Access-Jwt-Assertion': `${header}.${claims}.${base64url(signature)}` },
    }), env);
  }
  return { health, calls };
}

export const requestMode = {
  async test() {
    let rejected = false;
    try { new Request('https://unit-test.example/certs', { redirect: 'error' }); }
    catch (error) { rejected = error instanceof TypeError; }
    assert(rejected, 'Reproduction: workerd should reject redirect:error');
    assert(new Request('https://unit-test.example/certs', { redirect: 'manual' }).redirect === 'manual', 'manual mode rejected');
    console.log('Confirmed: workerd rejects redirect:error before making a network request.');
  },
};

export const authentication = {
  async test() {
    const f = await fixture();
    for (const aud of [AUD, [AUD]]) {
      const response = await f.health(aud);
      assert(response.status === 200, `Authenticated health expected 200, got ${response.status}`);
    }
    assert(f.calls.jwks === 1, 'JWKS cache not reused');
    const wrongAudience = await f.health(['b'.repeat(64)]);
    assert(wrongAudience.status === 403 && (await wrongAudience.json()).authReason === 'audience_mismatch', 'Audience guard weakened');
    const forged = await f.health([AUD], true);
    assert(forged.status === 403 && (await forged.json()).authReason === 'signature_mismatch', 'Forged signature accepted');
    assert(f.calls.reads === 0 && f.calls.writes === 0, 'Health/auth touched KV');
  },
};

export const redirects = {
  async test() {
    for (const status of [301, 302, 303, 307, 308]) {
      const f = await fixture(status);
      const response = await f.health();
      assert(response.status === 503 && (await response.json()).error === 'access_keys_unavailable', 'Redirect must fail closed');
      assert(f.calls.jwks === 1 && f.calls.reads === 0 && f.calls.writes === 0, 'Redirect reached storage or was followed');
    }
  },
};
