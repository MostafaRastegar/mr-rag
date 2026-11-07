"use client";

import { useState, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import {
  ChevronDown,
  ChevronUp,
  FileText,
  Copy,
  Check,
} from "lucide-react";

/* آیکون‌های تزئینی lucide — accessible-name ندارند (R-39) */
const HiddenIcon = ({ children }: { children: React.ReactNode }) => (
  <span aria-hidden="true">{children}</span>
);
import type { SourceItem } from "@/lib/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: SourceItem[];
  streaming?: boolean;
}

interface MessageBubbleProps {
  message: Message;
}

/* ------------------------------------------------------------------ */
/*  Custom Markdown components                                        */
/* ------------------------------------------------------------------ */

function CodeBlock({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  const match = /language-(\w+)/.exec(className ?? "");
  const code = String(children ?? "").replace(/\n$/, "");
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = code;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div
      className="group relative my-3 overflow-hidden rounded-xl border border-zinc-300 dark:border-zinc-600"
      dir="ltr"
    >
      {/* header bar */}
      {match && (
        <div className="flex items-center justify-between bg-zinc-200 px-3 py-1.5 text-[10px] font-medium text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400">
          <span>{match[1]}</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] opacity-0 transition-opacity hover:bg-zinc-300 group-hover:opacity-100 dark:hover:bg-zinc-600"
          >
            <HiddenIcon>{copied ? <Check size={11} /> : <Copy size={11} />}</HiddenIcon>
            {copied ? "کپی شد" : "کپی"}
          </button>
        </div>
      )}
      <pre className="overflow-x-auto p-3 text-xs leading-relaxed">
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}

function InlineCode(props: React.HTMLProps<HTMLElement>) {
  return (
    <code
      className="rounded-md bg-zinc-200 px-1.5 py-0.5 text-xs font-mono text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200"
      dir="ltr"
      {...props}
    />
  );
}

function Table(props: React.HTMLProps<HTMLTableElement>) {
  return (
    <div className="my-3 overflow-x-auto" dir="ltr">
      <table className="w-full border-collapse text-xs" {...props} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [showSources, setShowSources] = useState(false);
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const hasText = message.text.length > 0;
  const hasSources =
    !isUser &&
    !!message.sources &&
    message.sources.some(
      (s) =>
        s.metadata?.url ||
        s.metadata?.original_filename ||
        s.metadata?.page_title ||
        s.metadata?.ref,
    );

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback for older browsers
      const ta = document.createElement("textarea");
      ta.value = message.text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const markdownComponents = useMemo(
    () => ({
      code({
        className,
        children,
      }: {
        className?: string;
        children?: React.ReactNode;
      }) {
        const isInline = !className?.startsWith("language-");
        return isInline ? (
          <InlineCode className={className}>{children}</InlineCode>
        ) : (
          <CodeBlock className={className}>{children}</CodeBlock>
        );
      },
      table: Table,
    }),
    [],
  );

  return (
    <div dir="rtl" className="flex justify-start">
      <div
        className={`group relative max-w-[85%] px-4 py-3 text-sm leading-relaxed msg-enter ${
          isUser
            ? "bg-blue-600 text-white rounded-2xl rounded-tr-[6px]"
            : "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100 rounded-2xl rounded-tl-[6px]"
        }`}
      >
        {/* role label */}
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider opacity-60">
          {isUser ? "شما" : "دستیار"}
        </p>

        {/* copy button — visible on hover for assistant messages */}
        {!isUser && !message.streaming && hasText && (
          <button
            onClick={() => void handleCopy()}
            className="absolute -left-10 top-3 flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-200 text-zinc-500 opacity-0 transition-opacity hover:bg-zinc-300 group-hover:opacity-100 dark:bg-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-600"
            title="کپی پاسخ"
            aria-label="کپی پاسخ"
          >
            <HiddenIcon>{copied ? <Check size={14} /> : <Copy size={14} />}</HiddenIcon>
          </button>
        )}

        {/* text — rendered as Markdown */}
        <div className="markdown-body">
          {message.text ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={markdownComponents}
            >
              {message.text}
            </ReactMarkdown>
          ) : message.streaming ? (
            ""
          ) : (
            "..."
          )}
          {message.streaming && (
            <span className="inline-block h-3 w-1 animate-pulse bg-current" aria-hidden="true" />
          )}
        </div>

        {/* source toggle */}
        {hasSources && (
          <div className="mt-3 border-t border-zinc-300 pt-2 dark:border-zinc-600">
            <button
              onClick={() => setShowSources((v) => !v)}
              className="flex items-center gap-1 text-xs font-medium text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              <HiddenIcon><FileText size={13} /></HiddenIcon>
              منابع ({message.sources!.length})
              {showSources ? (
                <HiddenIcon><ChevronUp size={14} /></HiddenIcon>
              ) : (
                <HiddenIcon><ChevronDown size={14} /></HiddenIcon>
              )}
            </button>

            {showSources && (
              <ul className="mt-2 space-y-2">
                {message.sources!.map((src, i) => {
                  return (
                    <li
                      key={i}
                      className="rounded-lg border border-zinc-200 bg-white/60 p-2 text-xs dark:border-zinc-700 dark:bg-zinc-900/60"
                    >
                      {(src.metadata?.url ||
                        src.metadata?.original_filename ||
                        src.metadata?.page_title ||
                        src.metadata?.ref) ? (
                        <p className="mt-1 text-[10px] text-zinc-400">
                          [{i + 1}] -
                          {src.metadata.url ? (
                            <a
                              href={String(src.metadata.url)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 underline hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                            >
                              {String(
                                src.metadata.page_title ||
                                  src.metadata.original_filename ||
                                  src.metadata.ref,
                              )}
                            </a>
                          ) : (
                            String(
                              src.metadata.page_title ||
                                src.metadata.original_filename ||
                                src.metadata.ref,
                            )
                          )}
                        </p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
