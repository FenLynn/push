// Run with node --test tests/shared-data-ingest.test.mjs; no deployment tooling.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createIngestWorker } from '../services/shared-data-ingest/worker.mjs';

const NOW = Date.parse('2026-10-08T03:00:00.000Z');
const AUD = 'a'.repeat(64);
const ISSUER = 'https://unit-test.cloudflareaccess.com';
const CLIENT_ID = 'test-client.access';
const base64url = value => Buffer.from(value).toString('base64url');
const keyPair = await crypto.subtle.generateKey(
  { name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
  true, ['sign', 'verify'],
);
const publicKey = { ...await crypto.subtle.exportKey('jwk', keyPair.publicKey), kid: 'current', alg: 'RS256', use: 'sig' };

async function token(overrides = {}, headerOverrides = {}, signingKey = keyPair.privateKey) {
  const header = base64url(JSON.stringify({ alg: 'RS256', kid: 'current', typ: 'JWT', ...headerOverrides }));
  const claims = base64url(JSON.stringify({
    type: 'app', iss: ISSUER, aud: [AUD], sub: '', common_name: CLIENT_ID,
    iat: NOW / 1000 - 10, exp: NOW / 1000 + 300, ...overrides,
  }));
  const signature = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', signingKey, new TextEncoder().encode(`${header}.${claims}`));
  return `${header}.${claims}.${base64url(signature)}`;
}

function fixture(options = {}) {
  const values = new Map();
  const calls = { jwks: 0, reads: 0, writes: [] };
  let time = NOW;
  const worker = createIngestWorker({
    now: () => time,
    fetcher: async (url, config) => {
      calls.jwks++;
      assert.equal(url, `${ISSUER}/cdn-cgi/access/certs`);
      assert.equal(config.redirect, 'error');
      if (options.fetcher) return options.fetcher(url, config);
      return new Response(JSON.stringify({ keys: options.keys || [publicKey] }));
    },
  });
  const env = {
    TEAM_DOMAIN: ISSUER, POLICY_AUD: AUD, ACCESS_CLIENT_ID: CLIENT_ID,
    SHARED_DATA_KV: {
      async get(key) { calls.reads++; return values.get(key) ?? null; },
      async put(key, raw, config) {
        if (options.writeFails) throw new Error('sensitive storage failure');
        calls.writes.push({ key, raw, config });
        values.set(key, raw);
      },
    },
  };
  return { worker, env, calls, values, advance: delta => { time += delta; } };
}

function envelope(overrides = {}) {
  return {
    schemaVersion: 1, module: 'push:smoke', generatedAt: '2026-10-08T03:00:00Z',
    source: { repository: 'FenLynn/push', commit: 'b'.repeat(40), runId: '123' },
    payload: { message: 'hello 中文' }, ...overrides,
  };
}

function request(jwt, body = envelope(), path = '/api/ingest', method = 'POST', extraHeaders = {}) {
  return new Request(`https://ingest.660415.xyz${path}`, {
    method,
    headers: { ...(jwt ? { 'Cf-Access-Jwt-Assertion': jwt } : {}), 'Content-Type': 'application/json', ...extraHeaders },
    ...(method === 'POST' ? { body: typeof body === 'string' ? body : JSON.stringify(body) } : {}),
  });
}

test('missing Access JWT is rejected before any external or KV operation', async () => {
  const f = fixture();
  assert.equal((await f.worker.fetch(request(null), f.env)).status, 401);
  assert.deepEqual(f.calls, { jwks: 0, reads: 0, writes: [] });
});

test('missing configuration and a default-hostname bypass fail closed', async () => {
  const f = fixture();
  assert.equal((await f.worker.fetch(request(null), { ...f.env, POLICY_AUD: '' })).status, 503);
  for (const url of ['https://test.workers.dev/api/ingest', 'http://ingest.660415.xyz/api/ingest']) {
    assert.equal((await f.worker.fetch(new Request(url), f.env)).status, 403);
  }
  assert.equal(f.calls.jwks, 0);
  assert.equal(f.calls.writes.length, 0);
});

test('valid service token writes only the registered key and preserves the payload', async () => {
  const f = fixture();
  const response = await f.worker.fetch(request(await token()), f.env);
  assert.equal(response.status, 200);
  assert.equal((await response.json()).key, 'v1:push:smoke:latest');
  assert.equal(f.calls.reads, 0);
  assert.equal(f.calls.writes.length, 1);
  assert.deepEqual(f.calls.writes[0].config, { expirationTtl: 86400 });
  const saved = JSON.parse(f.calls.writes[0].raw);
  assert.deepEqual(saved.payload, envelope().payload);
  assert.equal(saved.receivedAt, new Date(NOW).toISOString());
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
  assert.equal(response.headers.get('Access-Control-Allow-Origin'), null);
});

test('wrong issuer, AUD, service identity, times, and algorithms are rejected', async () => {
  const variants = [
    [{ iss: 'https://evil.example' }], [{ aud: ['b'.repeat(64)] }], [{ aud: AUD }],
    [{ type: 'org' }], [{ exp: NOW / 1000 }], [{ iat: NOW / 1000 + 31 }],
    [{ nbf: NOW / 1000 + 1 }], [{ exp: '1234' }], [{ sub: 'human', email: 'user@example.com' }],
    [{ common_name: 'another.access' }], [{ common_name: '' }], [{}, { alg: 'none' }],
    [{}, { crit: ['something'] }], [{}, { kid: '' }],
  ];
  for (const [claims, headers] of variants) {
    const f = fixture();
    assert.equal((await f.worker.fetch(request(await token(claims, headers)), f.env)).status, 403);
    assert.equal(f.calls.writes.length, 0);
    assert.equal(f.calls.jwks, 0);
  }
});

test('a forged signature and malformed JWT cannot write', async () => {
  const jwt = await token();
  const parts = jwt.split('.');
  parts[2] = base64url(new Uint8Array(256));
  for (const value of ['not-a-jwt', 'a.b.c', parts.join('.')]) {
    const f = fixture();
    assert.equal((await f.worker.fetch(request(value), f.env)).status, 403);
    assert.equal(f.calls.writes.length, 0);
  }
});

test('JWKS cache is reused and unknown-key refreshes are bounded', async () => {
  const f = fixture();
  const jwt = await token();
  assert.equal((await f.worker.fetch(request(jwt, null, '/api/health', 'GET'), f.env)).status, 200);
  assert.equal((await f.worker.fetch(request(jwt, null, '/api/health', 'GET'), f.env)).status, 200);
  for (let i = 0; i < 3; i++) {
    assert.equal((await f.worker.fetch(request(await token({}, { kid: `missing-${i}` })), f.env)).status, 403);
  }
  assert.equal(f.calls.jwks, 1);
  assert.equal(f.calls.reads, 0);
  assert.equal(f.calls.writes.length, 0);
  f.advance(61000);
  assert.equal((await f.worker.fetch(request(await token({}, { kid: 'missing-4' })), f.env)).status, 403);
  assert.equal(f.calls.jwks, 2);
});

test('key rotation imports the new key after the bounded refresh interval', async () => {
  const rotated = { ...publicKey, kid: 'rotated' };
  let keys = [publicKey];
  const f = fixture({ fetcher: async () => new Response(JSON.stringify({ keys })) });
  const health = '/api/health';
  assert.equal((await f.worker.fetch(request(await token(), null, health, 'GET'), f.env)).status, 200);
  keys = [publicKey, rotated];
  f.advance(61000);
  assert.equal((await f.worker.fetch(request(await token({}, { kid: 'rotated' }), null, health, 'GET'), f.env)).status, 200);
  assert.equal(f.calls.jwks, 2);
});

test('JWKS outages never fall back to trusting a decoded JWT', async () => {
  const f = fixture({ fetcher: async () => new Response('down', { status: 503 }) });
  const response = await f.worker.fetch(request(await token()), f.env);
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, 'access_keys_unavailable');
  assert.equal(f.calls.writes.length, 0);
  assert.equal(f.calls.reads, 0);
});

test('expired key caches fail closed when refresh is unavailable', async () => {
  let available = true;
  const f = fixture({ fetcher: async () => available
    ? new Response(JSON.stringify({ keys: [publicKey] })) : new Response('down', { status: 503 }) });
  assert.equal((await f.worker.fetch(request(await token(), null, '/api/health', 'GET'), f.env)).status, 200);
  f.advance(3601000);
  available = false;
  const jwt = await token({ iat: (NOW + 3601000) / 1000 | 0, exp: (NOW + 3901000) / 1000 | 0 });
  assert.equal((await f.worker.fetch(request(jwt), f.env)).status, 503);
  assert.equal(f.calls.writes.length, 0);
});

test('unknown modules, empty payloads, arbitrary keys, and invalid metadata are rejected', async () => {
  const invalid = [
    envelope({ module: 'push:life' }), envelope({ key: 'settings:sensitive:v1' }),
    envelope({ payload: null }), envelope({ payload: {} }), envelope({ payload: [] }), envelope({ payload: 'text' }),
    envelope({ schemaVersion: 2 }), envelope({ source: { repository: 'FenLynn/academic' } }),
    envelope({ source: { repository: 'FenLynn/push', cookie: 'must-not-be-stored' } }),
    envelope({ source: { repository: 'FenLynn/push', commit: 'not-a-commit' } }),
    envelope({ source: { repository: 'FenLynn/push', runId: 123 } }),
    envelope({ generatedAt: '2026-10-08T03:06:00Z' }), envelope({ generatedAt: '2026-02-30T03:00:00Z' }),
    envelope({ generatedAt: '2026-10-08 03:00:00' }),
  ];
  const jwt = await token();
  for (const body of invalid) {
    const f = fixture();
    assert.equal((await f.worker.fetch(request(jwt, body), f.env)).status, 400);
    assert.equal(f.calls.writes.length, 0);
  }
});

test('malformed JSON, media types, and body size are checked before KV operations', async () => {
  const f = fixture();
  const jwt = await token();
  assert.equal((await f.worker.fetch(request(jwt, '{'), f.env)).status, 400);
  assert.equal((await f.worker.fetch(request(jwt, envelope(), '/api/ingest', 'POST', { 'Content-Type': 'text/plain' }), f.env)).status, 415);
  assert.equal((await f.worker.fetch(request(jwt, envelope(), '/api/ingest', 'POST', { 'Content-Length': '1048577' }), f.env)).status, 413);
  assert.equal((await f.worker.fetch(request(jwt, envelope({ payload: { text: 'x'.repeat(1048576) } })), f.env)).status, 413);
  assert.equal(f.calls.reads, 0);
  assert.equal(f.calls.writes.length, 0);
});

test('read endpoint is authenticated and does not mutate snapshots', async () => {
  const f = fixture();
  const path = '/api/status?module=push%3Asmoke';
  assert.equal((await f.worker.fetch(request(null, null, path, 'GET'), f.env)).status, 401);
  const jwt = await token();
  assert.equal((await f.worker.fetch(request(jwt, null, path, 'GET'), f.env)).status, 404);
  await f.worker.fetch(request(jwt), f.env);
  const response = await f.worker.fetch(request(jwt, null, path, 'GET'), f.env);
  assert.equal(response.status, 200);
  assert.deepEqual((await response.json()).snapshot.payload, envelope().payload);
  assert.equal(f.calls.writes.length, 1);
});

test('no delete, arbitrary read, or wildcard module endpoint is exposed', async () => {
  const f = fixture();
  const jwt = await token();
  assert.equal((await f.worker.fetch(request(jwt, null, '/api/ingest', 'DELETE'), f.env)).status, 405);
  assert.equal((await f.worker.fetch(request(jwt, null, '/api/status?module=settings', 'GET'), f.env)).status, 400);
  assert.equal((await f.worker.fetch(request(jwt, null, '/api/delete', 'GET'), f.env)).status, 404);
  assert.equal(f.calls.reads, 0);
  assert.equal(f.calls.writes.length, 0);
});

test('custom registries are explicit, and duplicate keys fail closed', async () => {
  const f = fixture();
  const jwt = await token();
  f.env.MODULE_REGISTRY_JSON = JSON.stringify({
    'academic:metrics': { key: 'v1:academic:metrics:latest', repository: 'FenLynn/academic' },
  });
  assert.equal((await f.worker.fetch(request(jwt, envelope()), f.env)).status, 400);
  const body = envelope({ module: 'academic:metrics', source: { repository: 'FenLynn/academic' } });
  assert.equal((await f.worker.fetch(request(jwt, body), f.env)).status, 200);
  assert.equal(f.calls.writes[0].key, 'v1:academic:metrics:latest');
  assert.deepEqual(f.calls.writes[0].config, {});
  f.env.MODULE_REGISTRY_JSON = JSON.stringify({
    'academic:metrics': { key: 'same:key', repository: 'FenLynn/academic' },
    'push:smoke': { key: 'same:key', repository: 'FenLynn/push' },
  });
  assert.equal((await f.worker.fetch(request(jwt, body), f.env)).status, 503);
  assert.equal(f.calls.writes.length, 1);
});

test('storage errors are sanitized and do not echo secrets', async () => {
  const f = fixture({ writeFails: true });
  const response = await f.worker.fetch(request(await token()), f.env);
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, 'kv_unavailable');
  assert.equal(f.calls.reads, 0);
});
