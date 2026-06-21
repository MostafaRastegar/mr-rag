"use client";

import { useState, useRef, type FormEvent } from "react";
import {
  Search,
  X,
  Loader2,
  Star,
  FileText,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { searchDocuments } from "@/lib/api";
import type { SearchResultItem } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

interface SearchPanelProps {
  onClose: () => void;
}

type Status = "idle" | "searching" | "done" | "error";

export default function SearchPanel({ onClose }: SearchPanelProps) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [errorMsg, setErrorMsg] = useState("");
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSearch = async (e?: FormEvent) => {
    e?.preventDefault();
    const q = query.trim();
    if (!q) return;

    setStatus("searching");
    setErrorMsg("");

    try {
      const resp = await searchDocuments(q, 20);
      setResults(resp.results);
      setStatus("done");
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "خطا در جستجو");
    }
  };

  const minScore = 0.15;

  return (
    <div
      dir="rtl"
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 pt-16"
      onClick={onClose}
    >
      <div
        className="mx-4 w-full max-w-2xl rounded-2xl bg-white shadow-xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-700">
          <h2 className="text-sm font-bold text-zinc-800 dark:text-zinc-200">
            جستجو در اسناد
          </h2>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
          >
            <X size={16} />
          </button>
        </div>

        {/* search input */}
        <form onSubmit={handleSearch} className="flex gap-2 px-4 py-3">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="عبارت مورد نظر را جستجو کنید…"
            className="flex-1 rounded-xl border border-zinc-300 bg-zinc-50 px-4 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:placeholder:text-zinc-500"
            autoFocus
          />
          <button
            type="submit"
            disabled={status === "searching" || !query.trim()}
            className="flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {status === "searching" ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Search size={16} />
            )}
            جستجو
          </button>
        </form>

        {/* results */}
        <div className="max-h-[60vh] overflow-y-auto px-4 pb-4">
          {status === "done" && results.length === 0 && (
            <p className="py-8 text-center text-sm text-zinc-400">
              هیچ نتیجه‌ای یافت نشد.
            </p>
          )}

          {results.length > 0 && (
            <div className="mb-2 text-xs text-zinc-400">
              {results.length} نتیجه یافت شد
            </div>
          )}

          <ul className="space-y-2">
            {results.map((item, i) => {
              const isLowScore = item.score < minScore;
              const expanded = expandedIndex === i;

              return (
                <li
                  key={i}
                  className={`rounded-xl border p-3 text-xs transition-colors ${
                    isLowScore
                      ? "border-zinc-100 bg-zinc-50 opacity-60 dark:border-zinc-800 dark:bg-zinc-900"
                      : "border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-800"
                  }`}
                >
                  {/* score badge */}
                  <div className="flex items-center gap-1.5">
                    <Star
                      size={12}
                      className={
                        item.score >= 0.7
                          ? "text-green-500"
                          : item.score >= minScore
                            ? "text-yellow-500"
                            : "text-zinc-300"
                      }
                    />
                    <span
                      className={`font-medium ${
                        item.score >= 0.7
                          ? "text-green-600 dark:text-green-400"
                          : item.score >= minScore
                            ? "text-yellow-600 dark:text-yellow-400"
                            : "text-zinc-400"
                      }`}
                    >
                      {(item.score * 100).toFixed(0)}%
                    </span>

                    {!!item.metadata?.title && (
                      <span className="mr-1 text-zinc-400">
                        — {String(item.metadata.title)}
                      </span>
                    )}
                  </div>

                  {/* content preview */}
                  <p
                    className={`mt-1.5 leading-relaxed text-zinc-600 dark:text-zinc-300 ${
                      expanded ? "" : "line-clamp-2"
                    }`}
                  >
                    {item.content}
                  </p>

                  {/* expand/collapse */}
                  {item.content.length > 150 && (
                    <button
                      onClick={() => setExpandedIndex(expanded ? null : i)}
                      className="mt-1 flex items-center gap-0.5 text-[10px] font-medium text-blue-500 hover:text-blue-600"
                    >
                      {expanded ? (
                        <>
                          کمتر <ChevronUp size={12} />
                        </>
                      ) : (
                        <>
                          بیشتر <ChevronDown size={12} />
                        </>
                      )}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>

          {/* error */}
          {status === "error" && (
            <p className="py-4 text-center text-sm text-red-500">{errorMsg}</p>
          )}
        </div>
      </div>
    </div>
  );
}
