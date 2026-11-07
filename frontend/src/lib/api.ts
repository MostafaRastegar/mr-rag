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

export interface StreamEvent {
  type: "sources" | "token" | "done";
  sources?: SourceItem[];
  text?: string;
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
): AsyncGenerator<StreamEvent> {
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
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buf += decoder.decode(value, { stream: true });

    // Split into complete SSE events (separated by blank lines).
    const parts = buf.split("\n\n");
    buf = parts.pop()!; // keep incomplete tail for next chunk

    for (const part of parts) {
      const event = parseSseEvent(part);
      if (event) yield event;
    }
  }

  // Flush any remaining tail
  if (buf.trim()) {
    const event = parseSseEvent(buf);
    if (event) yield event;
  }
}

function parseSseEvent(block: string): StreamEvent | null {
  let eventType = "";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!eventType) return null;
  const data = dataLines.join("\n");
  switch (eventType) {
    case "sources":
      return { type: "sources", sources: JSON.parse(data) as SourceItem[] };
    case "token":
      return { type: "token", text: JSON.parse(data) as string };
    case "done":
      return { type: "done" };
    default:
      return null;
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

/* ------------------------------------------------------------------ */
/*  Confluence                                                         */
/* ------------------------------------------------------------------ */

export interface ConfluenceCreds {
  base_url: string;
  auth_type: "bearer" | "basic";
  token: string;
  email?: string | null;
  username?: string | null;
}

export interface ConfluenceTestResponse {
  ok: boolean;
  user: string | null;
  spaces_count: number | null;
}

export interface ConfluenceSpaceItem {
  key: string;
  name: string;
}

export interface ConfluenceSpacesResponse {
  spaces: ConfluenceSpaceItem[];
}

export interface ConfluencePageItem {
  id: string;
  title: string;
  space_key: string;
  url: string;
  version: string | null;
}

export interface ConfluencePagesResponse {
  pages: ConfluencePageItem[];
  has_more: boolean;
}

export interface ConfluenceIndexRequest extends ConfluenceCreds {
  mode: "ids" | "space" | "subtree";
  page_ids?: string[] | null;
  space_key?: string | null;
  root_page_id?: string | null;
  recursive?: boolean;
}

export interface ConfluenceIndexResponse {
  status: string;
  pages_indexed: number;
  pages_failed: number;
  chunks_ingested: number;
  errors: { page_id: string; page_title: string; error: string }[];
}

export interface ConfluenceSyncRequest extends ConfluenceIndexRequest {}

export interface ConfluenceSyncResponse extends ConfluenceIndexResponse {}

export interface ConfluenceStatusResponse {
  last_sync: number | null;
  duration_seconds: number | null;
  pages_indexed: number | null;
  pages_failed: number | null;
  chunks_ingested: number | null;
  error: string | null;
}

export async function testConfluence(
  creds: ConfluenceCreds,
): Promise<ConfluenceTestResponse> {
  const res = await fetch(`${API_BASE}/confluence/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(creds),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Confluence test failed (${res.status}): ${err}`);
  }
  return res.json();
}

export async function getConfluenceSpaces(
  creds: ConfluenceCreds & { limit?: number },
): Promise<ConfluenceSpacesResponse> {
  const res = await fetch(`${API_BASE}/confluence/spaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(creds),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Confluence spaces failed (${res.status}): ${err}`);
  }
  return res.json();
}

export async function getConfluencePages(
  creds: ConfluenceCreds & {
    space_key?: string | null;
    parent_page_id?: string | null;
    start?: number;
    limit?: number;
  },
): Promise<ConfluencePagesResponse> {
  const res = await fetch(`${API_BASE}/confluence/pages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(creds),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Confluence pages failed (${res.status}): ${err}`);
  }
  return res.json();
}

export async function indexConfluence(
  request: ConfluenceIndexRequest,
): Promise<ConfluenceIndexResponse> {
  const res = await fetch(`${API_BASE}/confluence/index`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Confluence index failed (${res.status}): ${err}`);
  }
  return res.json();
}

export async function syncConfluence(
  request: ConfluenceSyncRequest,
): Promise<ConfluenceSyncResponse> {
  const res = await fetch(`${API_BASE}/confluence/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Confluence sync failed (${res.status}): ${err}`);
  }
  return res.json();
}

export async function getConfluenceStatus(): Promise<ConfluenceStatusResponse> {
  const res = await fetch(`${API_BASE}/confluence/status`);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Confluence status failed (${res.status}): ${err}`);
  }
  return res.json();
}
