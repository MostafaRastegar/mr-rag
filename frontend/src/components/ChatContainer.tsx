"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Loader2,
  WifiOff,
  Square,
  RotateCcw,
  Upload,
  Search,
  FileText,
  Activity,
} from "lucide-react";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import type { Message } from "./MessageBubble";
import Sidebar from "./Sidebar";
import FileUpload from "./FileUpload";
import type { UploadResult } from "./FileUpload";
import SearchPanel from "./SearchPanel";
import DocumentsPanel from "./DocumentsPanel";
import AdminPanel from "./AdminPanel";
import { sendChat, chatStream, getHealth } from "@/lib/api";
import type { ChatMessage, HealthResponse } from "@/lib/api";
import { getConversation, saveConversation } from "@/lib/db";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

let _id = 0;
function nextId() {
  return `msg_${++_id}`;
}

function generateId(): string {
  return crypto.randomUUID();
}

const WELCOME_TEXT = "سلام! من دستیار هوشمند شما هستم. هر سوالی دارید بپرسید.";

/**
 * Regeneration marker – appended to questions to bust the RAG exact cache.
 * Stripped from display text & IndexedDB titles automatically.
 */
const REGEN_MARKER = "/*__regen__";

/** Returns the "clean" question (without regeneration marker & suffix). */
function cleanQuestion(raw: string): string {
  const idx = raw.indexOf(REGEN_MARKER);
  return idx >= 0 ? raw.slice(0, idx).trim() : raw;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function ChatContainer() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    { id: nextId(), role: "assistant", text: WELCOME_TEXT },
  ]);
  const [loading, setLoading] = useState(false);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarRefreshTrigger, setSidebarRefreshTrigger] = useState(0);
  const [showUpload, setShowUpload] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [showDocuments, setShowDocuments] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef(messages);
  /* keep ref in sync */
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  /* scroll to bottom on new messages */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* periodic health check */
  useEffect(() => {
    const check = async () => {
      try {
        const h = await getHealth();
        setHealth(h);
        setHealthError(false);
      } catch {
        setHealth(null);
        setHealthError(true);
      }
    };
    check();
    const interval = setInterval(check, 30_000);
    return () => clearInterval(interval);
  }, []);

  /* -------------------------------------------------------------- */
  /*  Persist messages to IndexedDB whenever they change             */
  /* -------------------------------------------------------------- */

  const persist = useCallback(async (id: string, msgs: Message[]) => {
    if (msgs.length <= 1 && msgs[0]?.role === "assistant") return;

    const firstUserMsg = msgs.find((m) => m.role === "user");
    const title = firstUserMsg ? firstUserMsg.text.slice(0, 60) : "مکالمه جدید";

    await saveConversation({
      id,
      title,
      messages: msgs,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    });
  }, []);

  const persistTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!conversationId) return;
    if (persistTimerRef.current) clearTimeout(persistTimerRef.current);
    persistTimerRef.current = setTimeout(async () => {
      await persist(conversationId, messagesRef.current);
      setSidebarRefreshTrigger((n) => n + 1);
    }, 500);
    return () => {
      if (persistTimerRef.current) clearTimeout(persistTimerRef.current);
    };
  }, [messages, conversationId, persist]);

  /* -------------------------------------------------------------- */
  /*  Conversation management                                        */
  /* -------------------------------------------------------------- */

  const startNewConversation = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setConversationId(null);
    setMessages([{ id: nextId(), role: "assistant", text: WELCOME_TEXT }]);
    setLastQuestion(null);
    setSidebarRefreshTrigger((n) => n + 1);
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    const conv = await getConversation(id);
    if (conv) {
      setConversationId(conv.id);
      setMessages(conv.messages);
      // find last user message
      const lastUser = [...conv.messages]
        .reverse()
        .find((m) => m.role === "user");
      setLastQuestion(lastUser?.text ?? null);
    }
    setSidebarRefreshTrigger((n) => n + 1);
  }, []);

  const switchConversation = useCallback(
    async (id: string) => {
      // abort any ongoing request
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
      if (conversationId && messagesRef.current.length > 1) {
        await persist(conversationId, messagesRef.current);
      }
      await loadConversation(id);
      setSidebarOpen(false);
    },
    [conversationId, loadConversation, persist],
  );

  /* -------------------------------------------------------------- */
  /*  Stop handler                                                   */
  /* -------------------------------------------------------------- */

  const handleStop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setLoading(false);
    // mark streaming message as done
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
    );
  }, []);

  /* -------------------------------------------------------------- */
  /*  Send handler                                                   */
  /* -------------------------------------------------------------- */

  const doSend = useCallback(
    async (question: string) => {
      if (loading) return;

      let currentId = conversationId;
      if (!currentId) {
        currentId = generateId();
        setConversationId(currentId);
      }

      const clean = cleanQuestion(question);
      setLastQuestion(clean);

      const userMsg: Message = { id: nextId(), role: "user", text: clean };
      const msgsAfterUser = [...messagesRef.current, userMsg];

      const assistantId = nextId();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        text: "",
        streaming: true,
      };
      const msgsAfterAssistant = [...msgsAfterUser, assistantMsg];

      setMessages(msgsAfterAssistant);
      setLoading(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const firstUser = msgsAfterUser.find((m) => m.role === "user");
      const title = firstUser ? firstUser.text.slice(0, 60) : "مکالمه جدید";
      await saveConversation({
        id: currentId,
        title,
        messages: msgsAfterAssistant,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      });
      setSidebarRefreshTrigger((n) => n + 1);

      // Build history from previous messages (excluding the current question and welcome message)
      const history: ChatMessage[] = messagesRef.current
        .filter((m) => m.role === "user" || m.role === "assistant")
        .filter((m) => m.id !== messagesRef.current[0]?.id) // exclude welcome
        .slice(-10) // keep last 10 turns
        .map((m) => ({ role: m.role, content: m.text }));

      let fullText = "";
      let finalSources = undefined as Message["sources"];

      try {
        const stream = chatStream(question, controller.signal, history);

        for await (const token of stream) {
          fullText += token;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, text: fullText } : m,
            ),
          );
        }

        // stream finished – fetch full response to get sources
        const chatResp = await sendChat(question, history);
        const finalMsg: Message = {
          id: assistantId,
          role: "assistant",
          text: chatResp.answer,
          sources: chatResp.sources,
          streaming: false,
        };

        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? finalMsg : m)),
        );
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // user stopped — keep partial text
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, streaming: false } : m,
            ),
          );
          return;
        }

        if (fullText) {
          try {
            const chatResp = await sendChat(question, history);
            finalSources = chatResp.sources;
          } catch {
            // ignore
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    text: fullText,
                    sources: finalSources,
                    streaming: false,
                  }
                : m,
            ),
          );
        } else {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    text: "⚠️ خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.",
                    streaming: false,
                  }
                : m,
            ),
          );
        }
      } finally {
        setLoading(false);
        abortRef.current = null;
      }
    },
    [loading, conversationId],
  );

  const handleRegenerate = useCallback(() => {
    if (lastQuestion) {
      // remove last assistant message
      const msgs = messagesRef.current;
      if (msgs.length > 0 && msgs[msgs.length - 1].role === "assistant") {
        setMessages(msgs.slice(0, -1));
      }
      // append RNG marker so the RAG cache miss → fresh answer
      const busted = `${lastQuestion} ${REGEN_MARKER}${generateId()}__*/`;
      doSend(busted);
    }
  }, [lastQuestion, doSend]);

  const handleFileSuccess = useCallback((result: UploadResult) => {
    // add a system message about the upload
    const systemMsg: Message = {
      id: nextId(),
      role: "assistant",
      text: `📄 **${result.fileName}** بارگذاری شد. ${result.chunks} قطعه استخراج شد.`,
    };
    setMessages((prev) => [...prev, systemMsg]);
    setHealth((prev) =>
      prev
        ? {
            ...prev,
            vector_store_count: prev.vector_store_count + result.chunks,
          }
        : prev,
    );
  }, []);

  /* -------------------------------------------------------------- */
  /*  Render                                                         */
  /* -------------------------------------------------------------- */

  return (
    <>
      <Sidebar
        activeConversationId={conversationId}
        onSelect={switchConversation}
        onNew={startNewConversation}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        refreshTrigger={sidebarRefreshTrigger}
      />

      {showUpload && (
        <FileUpload
          onSuccess={handleFileSuccess}
          onClose={() => setShowUpload(false)}
        />
      )}

      {showSearch && <SearchPanel onClose={() => setShowSearch(false)} />}
      {showDocuments && (
        <DocumentsPanel onClose={() => setShowDocuments(false)} />
      )}
      {showAdmin && <AdminPanel onClose={() => setShowAdmin(false)} />}

      <div className="mx-auto flex h-dvh w-full max-w-3xl flex-col">
        {/* header */}
        <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 pr-12 dark:border-zinc-700">
          <h1 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
            دستیار هوشمند
          </h1>

          <div className="flex items-center gap-2">
            {/* search button */}
            <button
              onClick={() => setShowSearch(true)}
              className="flex h-7 items-center gap-1 rounded-lg bg-zinc-100 px-2.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
              title="جستجو در اسناد"
            >
              <Search size={13} />
              جستجو
            </button>

            {/* upload button */}
            <button
              onClick={() => setShowUpload(true)}
              className="flex h-7 items-center gap-1 rounded-lg bg-zinc-100 px-2.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
              title="بارگذاری سند"
            >
              <Upload size={13} />
              سند
            </button>

            {/* documents button */}
            <button
              onClick={() => setShowDocuments(true)}
              className="flex h-7 items-center gap-1 rounded-lg bg-zinc-100 px-2.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
              title="مدیریت اسناد"
            >
              <FileText size={13} />
              اسناد
            </button>

            {/* admin button */}
            <button
              onClick={() => setShowAdmin(true)}
              className="flex h-7 items-center gap-1 rounded-lg bg-zinc-100 px-2.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
              title="پنل مدیریت"
            >
              <Activity size={13} />
              مدیریت
            </button>

            {/* health badge */}
            <div className="flex items-center gap-1.5 text-xs">
              {healthError ? (
                <span className="flex items-center gap-1 text-red-500">
                  <WifiOff size={12} />
                  قطع
                </span>
              ) : health ? (
                <span className="flex items-center gap-1 text-green-600">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-500" />
                  {health.vector_store_count} سند
                </span>
              ) : (
                <span className="flex items-center gap-1 text-zinc-400">
                  <Loader2 size={12} className="animate-spin" />
                  در حال بررسی …
                </span>
              )}
            </div>
          </div>
        </header>

        {/* messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          <div className="space-y-4">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
          </div>
          <div ref={bottomRef} />
        </div>

        {/* controls during loading */}
        {loading && (
          <div className="flex items-center justify-center gap-2 border-t border-zinc-200 bg-white px-4 py-2 dark:border-zinc-700 dark:bg-zinc-900">
            <button
              onClick={handleStop}
              className="flex items-center gap-1.5 rounded-lg bg-red-500 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-red-600"
            >
              <Square size={13} />
              توقف
            </button>
            <span className="text-xs text-zinc-400">در حال تولید پاسخ…</span>
          </div>
        )}

        {/* regenerate button (when not loading and last is assistant) */}
        {!loading &&
          messages.length > 1 &&
          messages[messages.length - 1].role === "assistant" &&
          !messages[messages.length - 1].streaming &&
          lastQuestion && (
            <div className="flex items-center justify-center border-t border-zinc-200 bg-white px-4 py-2 dark:border-zinc-700 dark:bg-zinc-900">
              <button
                onClick={handleRegenerate}
                className="flex items-center gap-1.5 rounded-lg bg-zinc-100 px-4 py-2 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
              >
                <RotateCcw size={13} />
                تولید مجدد
              </button>
            </div>
          )}

        {/* input */}
        <ChatInput onSend={doSend} disabled={loading} />
      </div>
    </>
  );
}
