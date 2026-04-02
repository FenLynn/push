const DEFAULT_LIMIT = 200;
const MAX_LIMIT = 400;

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, x-snapshot-key',
  'Content-Type': 'application/json',
};

function jsonResponse(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      ...corsHeaders,
      ...extraHeaders,
    },
  });
}

function errorResponse(message, status = 500) {
  return jsonResponse({ error: message }, status);
}

function clampPositiveInteger(value, fallback, max) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return fallback;
  return Math.min(max, Math.floor(numeric));
}

function normalizeDateInput(value = '') {
  const text = String(value || '').trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : '';
}

function buildFilteredJournals(items = []) {
  const counts = new Map();
  items.forEach(item => {
    const key = String(item?.journalRaw || '').trim();
    if (!key) return;
    const current = counts.get(key) || { name: key, label: item?.journal || key, count: 0 };
    current.count += 1;
    counts.set(key, current);
  });
  return Array.from(counts.values()).sort((left, right) => left.label.localeCompare(right.label));
}

function applyFilters(snapshot = {}, url) {
  const filters = {
    journal: String(url.searchParams.get('journal') || '').trim(),
    from: normalizeDateInput(url.searchParams.get('from')),
    to: normalizeDateInput(url.searchParams.get('to')),
    search: String(url.searchParams.get('search') || '').trim().toLowerCase().slice(0, 120),
  };
  const limit = clampPositiveInteger(url.searchParams.get('limit'), DEFAULT_LIMIT, MAX_LIMIT);
  const sourceItems = Array.isArray(snapshot.items) ? snapshot.items : [];

  const dateFilteredItems = sourceItems.filter(item => {
    const dateKey = String(item?.dateKey || '').trim();
    if (filters.journal && String(item?.journalRaw || '').trim() !== filters.journal) return false;
    if (filters.from && dateKey && dateKey < filters.from) return false;
    if (filters.to && dateKey && dateKey > filters.to) return false;
    return true;
  });

  const searchedItems = dateFilteredItems.filter(item => {
    if (!filters.search) return true;
    const haystack = [
      item?.title,
      item?.journal,
      item?.journalRaw,
      item?.abstract,
      item?.authorsText,
      item?.doi,
      ...(Array.isArray(item?.keywords) ? item.keywords : []),
    ].join(' ').toLowerCase();
    return haystack.includes(filters.search);
  });

  return {
    items: searchedItems.slice(0, limit),
    journals: buildFilteredJournals(dateFilteredItems),
    total: searchedItems.length,
    filters,
    limit,
  };
}

function buildCacheHeaders(env, snapshot = {}) {
  const ttl = Math.max(30, Number(env.OPTICS_SNAPSHOT_CACHE_TTL || 120));
  const isPrivate = Boolean(String(env.SNAPSHOT_ACCESS_KEY || '').trim());
  return {
    'Cache-Control': `${isPrivate ? 'private' : 'public'}, max-age=${ttl}, s-maxage=${ttl}`,
    ...(snapshot?.meta?.etag ? { ETag: snapshot.meta.etag } : {}),
  };
}

async function handleOpticsSnapshot(request, env) {
  const requiredKey = String(env.SNAPSHOT_ACCESS_KEY || '').trim();
  if (requiredKey) {
    const providedKey = String(request.headers.get('x-snapshot-key') || '').trim();
    if (providedKey !== requiredKey) {
      return errorResponse('Unauthorized snapshot request', 401);
    }
  }

  const kvKey = String(env.OPTICS_SNAPSHOT_KV_KEY || 'snapshot:paper:optics:latest').trim();
  const snapshot = await env.SNAPSHOT_KV?.get(kvKey, 'json');
  if (!snapshot || typeof snapshot !== 'object') {
    return errorResponse('Optics snapshot not found', 404);
  }

  const url = new URL(request.url);
  const filtered = applyFilters(snapshot, url);
  return jsonResponse({
    items: filtered.items,
    journals: filtered.journals,
    meta: {
      ...(snapshot.meta || {}),
      total: filtered.total,
      returned: filtered.items.length,
      journalCount: filtered.journals.length,
      filters: filtered.filters,
      limit: filtered.limit,
    },
  }, 200, buildCacheHeaders(env, snapshot));
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    if (url.pathname === '/health') {
      return jsonResponse({ ok: true, service: 'push-snapshot-worker' });
    }
    if (url.pathname === '/api/snapshots/optics') {
      return handleOpticsSnapshot(request, env);
    }
    return errorResponse('Not Found', 404);
  },
};