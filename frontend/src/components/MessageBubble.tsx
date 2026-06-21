"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  FileText,
  Star,
  Copy,
  Check,
} from "lucide-react";
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

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [showSources, setShowSources] = useState(false);
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const hasSources = !isUser && message.sources && message.sources.length > 0;

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

  return (
    <div dir="rtl" className="flex justify-start">
      <div
        className={`group relative max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
        }`}
      >
        {/* role label */}
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider opacity-60">
          {isUser ? "شما" : "دستیار"}
        </p>

        {/* copy button — visible on hover for assistant messages */}
        {!isUser && !message.streaming && message.text && (
          <button
            onClick={handleCopy}
            className="absolute -left-10 top-3 flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-200 text-zinc-500 opacity-0 transition-opacity hover:bg-zinc-300 group-hover:opacity-100 dark:bg-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-600"
            title="کپی پاسخ"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
        )}

        {/* text */}
        <div className="whitespace-pre-wrap break-words">
          {message.text || (message.streaming ? "" : "...")}
          {message.streaming && (
            <span className="inline-block h-3 w-1 animate-pulse bg-current" />
          )}
        </div>

        {/* source toggle */}
        {hasSources && (
          <div className="mt-3 border-t border-zinc-300 pt-2 dark:border-zinc-600">
            <button
              onClick={() => setShowSources((v) => !v)}
              className="flex items-center gap-1 text-xs font-medium text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              <FileText size={13} />
              منابع ({message.sources!.length})
              {showSources ? (
                <ChevronUp size={14} />
              ) : (
                <ChevronDown size={14} />
              )}
            </button>

            {showSources && (
              <ul className="mt-2 space-y-2">
                {message.sources!.map((src, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-zinc-200 bg-white/60 p-2 text-xs dark:border-zinc-700 dark:bg-zinc-900/60"
                  >
                    <div className="flex items-center gap-1 text-zinc-400">
                      <Star size={11} />
                      <span>{(src.score * 100).toFixed(0)}%</span>
                    </div>
                    <p className="mt-1 leading-relaxed text-zinc-600 dark:text-zinc-300 line-clamp-3">
                      {src.content}
                    </p>
                    {src.metadata?.title && (
                      <p className="mt-1 text-[10px] text-zinc-400">
                        {src.metadata.title as string}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
