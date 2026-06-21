/**
 * API client for the mr-rag backend.
 *
 * All endpoints return typed responses as defined in app/api/schemas.py.
 * The backend runs on APP_HOST:APP_PORT (default http://127.0.0.1:8080).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8080";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface SourceItem {
  content: string;
  metadata: Record<string, unknown>;
  score: number;
}

export interface ChatResponse {
  answer: string;
  sources: SourceItem[];
}

export interface HealthResponse {
  status: string;
  vector_store_count: number;
}

export interface IngestResponse {
  status: string;
  chunks_ingested: number;
}

export interface UploadResponse {
  status: string;
  file_name: string;
  chunks_ingested: number;
  message: string;
}

export interface SearchResultItem {
  content: string;
  metadata: Record<string, unknown>;
  score: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  results: SearchResultItem[];
}

/* ------------------------------------------------------------------ */
/*  Chat (full response)                                               */
/* ------------------------------------------------------------------ */

export async function sendChat(question: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Chat failed (${res.status}): ${err}`);
  }
  return res.json();
}

/* ------------------------------------------------------------------ */
/*  Chat (streaming – Server-Sent Events)                              */
/* ------------------------------------------------------------------ */

/**
 * Returns an `AsyncGenerator` that yields token strings as they arrive
 * via SSE. Usage:
 *
 * ```ts
 * for await (const token of chatStream("Hello?")) {
 *   console.log(token);
 * }
 * ```
 */
export async function* chatStream(
  question: string,
  signal?: AbortSignal,
): AsyncGenerator<string> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Chat stream failed (${res.status}): ${err}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body for stream");

  const decoder = new TextDecoder();
  const buffer: string[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    // The backend streams raw SSE text; each chunk may contain one or
    // more data lines.  We forward them as-is for the UI to append.
    buffer.push(chunk);

    // yield whatever we have so the UI stays responsive
    for (const ch of buffer.splice(0)) {
      yield ch;
    }
  }
}

/* ------------------------------------------------------------------ */
/*  Health check                                                       */
/* ------------------------------------------------------------------ */

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed (${res.status})`);
  return res.json();
}

/* ------------------------------------------------------------------ */
/*  Ingest                                                             */
/* ------------------------------------------------------------------ */

export async function ingestFile(filePath: string): Promise<IngestResponse> {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Ingest failed (${res.status}): ${err}`);
  }
  return res.json();
}

/* ------------------------------------------------------------------ */
/*  Search (direct vector search, no LLM)                              */
/* ------------------------------------------------------------------ */

export async function searchDocuments(
  query: string,
  top_k: number = 10,
): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Search failed (${res.status}): ${err}`);
  }
  return res.json();
}

/* ------------------------------------------------------------------ */
/*  Upload file  (multipart)                                           */
/* ------------------------------------------------------------------ */

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Upload failed (${res.status}): ${err}`);
  }
  return res.json();
}
