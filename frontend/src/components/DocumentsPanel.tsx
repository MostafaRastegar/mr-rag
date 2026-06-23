"use client";

import { useState, useEffect } from "react";
import {
  X,
  Loader2,
  FileText,
  Trash2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Database,
  RefreshCw,
} from "lucide-react";
import { getDocuments, deleteDocument } from "@/lib/api";
import type { DocumentItem, DocumentListResponse } from "@/lib/api";

interface DocumentsPanelProps {
  onClose: () => void;
}

type Status = "loading" | "loaded" | "error" | "deleting";

export default function DocumentsPanel({ onClose }: DocumentsPanelProps) {
  const [status, setStatus] = useState<Status>("loading");
  const [data, setData] = useState<DocumentListResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = async () => {
    setStatus("loading");
    setErrorMsg("");
    try {
      const resp = await getDocuments();
      setData(resp);
      setStatus("loaded");
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "خطا در دریافت اسناد");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await deleteDocument(id);
      setData((prev) =>
        prev
          ? {
              ...prev,
              total: prev.total - 1,
              documents: prev.documents.filter((d) => d.id !== id),
            }
          : prev,
      );
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "خطا در حذف سند");
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleDateString("fa-IR", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatFileType = (t: string) => {
    const map: Record<string, string> = {
      json: "JSON",
      md: "MD",
      txt: "TXT",
      pdf: "PDF",
    };
    return map[t] ?? t.toUpperCase();
  };

  return (
    <div
      dir="rtl"
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 pt-12"
      onClick={onClose}
    >
      <div
        className="mx-4 w-full max-w-2xl rounded-2xl bg-white shadow-xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-700">
          <h2 className="flex items-center gap-2 text-sm font-bold text-zinc-800 dark:text-zinc-200">
            <FileText size={16} />
            مدیریت اسناد
          </h2>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
          >
            <X size={16} />
          </button>
        </div>

        {/* body */}
        <div className="max-h-[70vh] overflow-y-auto px-4 pb-4">
          {/* error banner */}
          {errorMsg && (
            <div className="mt-3 flex items-center gap-1.5 rounded-lg bg-red-50 p-2.5 text-xs text-red-600 dark:bg-red-950 dark:text-red-400">
              <AlertCircle size={14} />
              {errorMsg}
            </div>
          )}

          {/* loading */}
          {status === "loading" && (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-zinc-400">
              <Loader2 size={18} className="animate-spin" />
              در حال دریافت اسناد …
            </div>
          )}

          {/* error state */}
          {status === "error" && !errorMsg && (
            <div className="py-8 text-center">
              <p className="text-sm text-zinc-400">خطا در دریافت اسناد</p>
              <button
                onClick={load}
                className="mt-3 flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-700"
              >
                <RefreshCw size={13} />
                تلاش مجدد
              </button>
            </div>
          )}

          {/* empty state */}
          {status === "loaded" && data && data.total === 0 && (
            <div className="flex flex-col items-center gap-2 py-12">
              <Database size={32} className="text-zinc-300 dark:text-zinc-600" />
              <p className="text-sm text-zinc-400">هیچ سندی یافت نشد</p>
            </div>
          )}

          {/* document list */}
          {status === "loaded" && data && data.total > 0 && (
            <>
              <div className="mb-2 mt-3 text-xs text-zinc-400">
                {data.total} سند
              </div>
              <ul className="space-y-2">
                {data.documents.map((doc) => {
                  const expanded = expandedId === doc.id;

                  return (
                    <li
                      key={doc.id}
                      className="rounded-xl border border-zinc-200 bg-white p-3 text-xs dark:border-zinc-700 dark:bg-zinc-800"
                    >
                      {/* top row */}
                      <div className="flex items-center gap-2">
                        <FileText
                          size={14}
                          className="shrink-0 text-blue-500"
                        />
                        <span className="flex-1 truncate font-medium text-zinc-800 dark:text-zinc-200">
                          {doc.original_filename}
                        </span>
                        <span
                          className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
                            doc.file_type === "json"
                              ? "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
                              : doc.file_type === "md"
                                ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                                : "bg-zinc-100 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300"
                          }`}
                        >
                          {formatFileType(doc.file_type)}
                        </span>
                      </div>

                      {/* metadata */}
                      <div className="mt-1.5 flex items-center gap-3 text-[10px] text-zinc-400">
                        <span>{doc.chunk_count} قطعه</span>
                        <span>{formatDate(doc.ingested_at)}</span>
                      </div>

                      {/* expandable detail */}
                      {expanded && (
                        <div className="mt-2 rounded-lg bg-zinc-50 p-2.5 text-[10px] text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
                          <div className="grid grid-cols-2 gap-1">
                            <span>شناسه:</span>
                            <span className="font-mono text-zinc-700 dark:text-zinc-300">
                              {doc.id}
                            </span>
                            <span>مسیر:</span>
                            <span className="truncate font-mono text-zinc-700 dark:text-zinc-300">
                              {doc.source_path}
                            </span>
                            <span>نوع:</span>
                            <span className="text-zinc-700 dark:text-zinc-300">
                              {doc.file_type}
                            </span>
                            <span>تعداد قطعات:</span>
                            <span className="text-zinc-700 dark:text-zinc-300">
                              {doc.chunk_count}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* actions */}
                      <div className="mt-2 flex items-center gap-1">
                        <button
                          onClick={() =>
                            setExpandedId(expanded ? null : doc.id)
                          }
                          className="flex items-center gap-0.5 rounded-md px-2 py-1 text-[10px] font-medium text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950"
                        >
                          {expanded ? (
                            <>
                              کمتر <ChevronUp size={11} />
                            </>
                          ) : (
                            <>
                              جزئیات <ChevronDown size={11} />
                            </>
                          )}
                        </button>

                        <button
                          onClick={() => handleDelete(doc.id)}
                          disabled={deletingId === doc.id}
                          className="mr-auto flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium text-red-500 hover:bg-red-50 disabled:opacity-50 dark:hover:bg-red-950"
                        >
                          {deletingId === doc.id ? (
                            <Loader2 size={11} className="animate-spin" />
                          ) : (
                            <Trash2 size={11} />
                          )}
                          حذف
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
