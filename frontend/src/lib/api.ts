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

export interface ChatMessage {
  role: string;
  content: string;
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

/* ------------------------------------------------------------------ */
/*  Document management                                                */
/* ------------------------------------------------------------------ */

export interface DocumentItem {
  id: string;
  filename: string;
  original_filename: string;
  source_path: string;
  file_type: string;
  chunk_count: number;
  ingested_at: number;
}

export interface DocumentListResponse {
  total: number;
  documents: DocumentItem[];
}

export interface DocumentDeleteResponse {
  status: string;
  deleted: boolean;
  chunks_removed: number;
}

export async function getDocuments(): Promise<DocumentListResponse> {
  const res = await fetch(`${API_BASE}/documents`);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to fetch documents (${res.status}): ${err}`);
  }
  return res.json();
}

export async function getDocument(id: string): Promise<DocumentItem> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(id)}`);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to fetch document (${res.status}): ${err}`);
  }
  return res.json();
}

export async function deleteDocument(
  id: string,
): Promise<DocumentDeleteResponse> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to delete document (${res.status}): ${err}`);
  }
  return res.json();
}

/* ------------------------------------------------------------------ */
/*  Admin                                                              */
/* ------------------------------------------------------------------ */

export interface AdminStatsResponse {
  vector_store_count: number;
  document_count: number;
  cache_embedding_size: number;
  cache_llm_size: number;
  cache_rag_size: number;
}

export interface SchedulerStatusResponse {
  last_fetch: string | null;
  total_documents: number | null;
  status: string | null;
  error_message: string | null;
}

export interface SchedulerRunResponse {
  status: string;
  message: string;
}

export interface CacheClearResponse {
  status: string;
  message: string;
}

export async function getAdminStats(): Promise<AdminStatsResponse> {
  const res = await fetch(`${API_BASE}/admin/stats`);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to fetch admin stats (${res.status}): ${err}`);
  }
  return res.json();
}

export async function getSchedulerStatus(): Promise<SchedulerStatusResponse> {
  const res = await fetch(`${API_BASE}/admin/scheduler/status`);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(
      `Failed to fetch scheduler status (${res.status}): ${err}`,
    );
  }
  return res.json();
}

export async function runScheduler(): Promise<SchedulerRunResponse> {
  const res = await fetch(`${API_BASE}/admin/scheduler/run`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to run scheduler (${res.status}): ${err}`);
  }
  return res.json();
}

export async function clearCache(): Promise<CacheClearResponse> {
  const res = await fetch(`${API_BASE}/admin/cache/clear`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to clear cache (${res.status}): ${err}`);
  }
  return res.json();
}

/* ------------------------------------------------------------------ */
/*  Metrics (Prometheus plain text)                                    */
/* ------------------------------------------------------------------ */

export async function getMetrics(): Promise<string> {
  const res = await fetch(`${API_BASE}/metrics`);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to fetch metrics (${res.status}): ${err}`);
  }
  return res.text();
}

/* ------------------------------------------------------------------ */
/*  Conversations                                                      */
/* ------------------------------------------------------------------ */

export interface ConversationMessageItem {
  role: string;
  content: string;
  timestamp?: number | null;
}

export interface ConversationItem {
  id: string;
  title: string;
  messages: ConversationMessageItem[];
  created_at: number;
  updated_at: number;
}

export interface ConversationListResponse {
  total: number;
  conversations: ConversationItem[];
}

export interface ConversationDeleteResponse {
  status: string;
  deleted: boolean;
}

export async function getConversations(
  limit: number = 50,
  offset: number = 0,
): Promise<ConversationListResponse> {
  const res = await fetch(
    `${API_BASE}/conversations?limit=${limit}&offset=${offset}`,
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to fetch conversations (${res.status}): ${err}`);
  }
  return res.json();
}

export async function getConversation(
  id: string,
): Promise<ConversationItem> {
  const res = await fetch(
    `${API_BASE}/conversations/${encodeURIComponent(id)}`,
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to fetch conversation (${res.status}): ${err}`);
  }
  return res.json();
}

export async function createConversation(
  title: string = "New Conversation",
  messages: ConversationMessageItem[] = [],
): Promise<ConversationItem> {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, messages }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Failed to create conversation (${res.status}): ${err}`);
  }
  return res.json();
}

export async function updateConversation(
  id: string,
  data: { title?: string; messages?: ConversationMessageItem[] },
): Promise<ConversationItem> {
  const res = await fetch(
    `${API_BASE}/conversations/${encodeURIComponent(id)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(
      `Failed to update conversation (${res.status}): ${err}`,
    );
  }
  return res.json();
}

export async function deleteConversationApi(
  id: string,
): Promise<ConversationDeleteResponse> {
  const res = await fetch(
    `${API_BASE}/conversations/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(
      `Failed to delete conversation (${res.status}): ${err}`,
    );
  }
  return res.json();
}

/* ------------------------------------------------------------------ */
/*  Search                                                             */
/* ------------------------------------------------------------------ */

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

export async function sendChat(
  question: string,
  messages: ChatMessage[] = [],
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, messages }),
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
  messages: ChatMessage[] = [],
): AsyncGenerator<string> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, messages }),
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
