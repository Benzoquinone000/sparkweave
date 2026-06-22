const DEFAULT_BACKEND_PORT = "8001";


function normalizeBase(value: string) {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

export function getApiBase() {
  const runtimeBase =
    typeof window !== "undefined" ? window.__SPARKWEAVE_RUNTIME_CONFIG__?.apiBase : undefined;
  const explicit =
    runtimeBase ||
    import.meta.env.VITE_API_BASE ||
    import.meta.env.NEXT_PUBLIC_API_BASE_EXTERNAL ||
    import.meta.env.NEXT_PUBLIC_API_BASE;
  if (explicit && explicit.trim()) {
    return normalizeBase(explicit.trim());
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:${DEFAULT_BACKEND_PORT}`;
  }
  return `http://localhost:${DEFAULT_BACKEND_PORT}`;
}

function getClientApiKey() {
  const runtimeKey =
    typeof window !== "undefined" ? window.__SPARKWEAVE_RUNTIME_CONFIG__?.apiKey : undefined;
  return (
    runtimeKey ||
    import.meta.env.VITE_SPARKWEAVE_API_KEY ||
    import.meta.env.NEXT_PUBLIC_SPARKWEAVE_API_KEY ||
    ""
  ).trim();
}

export function appendApiKeyQuery(url: string) {
  const apiKey = getClientApiKey();
  if (!apiKey) return url;
  const hashIndex = url.indexOf("#");
  const base = hashIndex >= 0 ? url.slice(0, hashIndex) : url;
  const hash = hashIndex >= 0 ? url.slice(hashIndex) : "";
  const separator = base.includes("?") ? "&" : "?";
  return `${base}${separator}sparkweave_api_key=${encodeURIComponent(apiKey)}${hash}`;
}

function withApiKeyHeader(headers?: HeadersInit) {
  const next = new Headers(headers);
  const apiKey = getClientApiKey();
  if (apiKey && !next.has("x-sparkweave-api-key")) {
    next.set("x-sparkweave-api-key", apiKey);
  }
  return next;
}

export function authorizedFetch(input: RequestInfo | URL, init?: RequestInit) {
  return fetch(input, {
    ...init,
    headers: withApiKeyHeader(init?.headers),
  });
}

export function apiUrl(path: string) {
  return `${getApiBase()}${path.startsWith("/") ? path : `/${path}`}`;
}

export function authenticatedResourceUrl(url: string) {
  const trimmed = url.trim();
  if (!trimmed) return "";
  if (/^(?:blob|data):/i.test(trimmed)) return trimmed;
  const apiBase = getApiBase();
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed === apiBase || trimmed.startsWith(`${apiBase}/`) ? appendApiKeyQuery(trimmed) : trimmed;
  }
  return appendApiKeyQuery(apiUrl(trimmed));
}

export function wsUrl(path: string) {
  const base = getApiBase().replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  return appendApiKeyQuery(`${base}${path.startsWith("/") ? path : `/${path}`}`);
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status = 0,
  ) {
    super(message);
  }
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    response = await authorizedFetch(apiUrl(path), {
      cache: "no-store",
      ...init,
      headers,
    });
  } catch (error) {
    throw new ApiError(error instanceof Error ? error.message : "Network error");
  }

  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (payload?.detail) detail = String(payload.detail);
    } catch {
      // Keep the status text fallback.
    }
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

export type SseEventHandler = (event: string, payload: Record<string, unknown>) => void;

export async function readSseResponse(
  response: Response,
  onEvent: SseEventHandler,
  failureMessage = "Stream request failed",
) {
  if (!response.ok) {
    throw new ApiError(`${failureMessage}: ${response.status}`, response.status);
  }
  if (!response.body) {
    throw new ApiError("Stream response did not return a response body", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const flushBlock = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    const raw = dataLines.join("\n");
    try {
      onEvent(event, JSON.parse(raw) as Record<string, unknown>);
    } catch {
      onEvent(event, { text: raw });
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split(/\n\n/);
    buffer = blocks.pop() ?? "";
    blocks.forEach(flushBlock);
  }
  buffer += decoder.decode();
  if (buffer.trim()) flushBlock(buffer.trim());
}
