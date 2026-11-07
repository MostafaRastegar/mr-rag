"use client";

import { useState, useEffect } from "react";
import {
  X,
  Loader2,
  Activity,
  Database,
  Cpu,
  Trash2,
  Play,
  AlertCircle,
  Check,
  RefreshCw,
  Clock,
} from "lucide-react";

/* آیکون‌های تزئینی lucide (R-39) */
const HiddenIcon = ({ children }: { children: React.ReactNode }) => (
  <span aria-hidden="true">{children}</span>
);
import {
  getAdminStats,
  getSchedulerStatus,
  runScheduler,
  clearCache,
} from "@/lib/api";
import type {
  AdminStatsResponse,
  SchedulerStatusResponse,
} from "@/lib/api";

interface AdminPanelProps {
  onClose: () => void;
}

export default function AdminPanel({ onClose }: AdminPanelProps) {
  const [stats, setStats] = useState<AdminStatsResponse | null>(null);
  const [scheduler, setScheduler] = useState<SchedulerStatusResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [schedulerRunning, setSchedulerRunning] = useState(false);
  const [cacheClearing, setCacheClearing] = useState(false);
  const [cacheMsg, setCacheMsg] = useState("");
  const [schedulerMsg, setSchedulerMsg] = useState("");

  const load = async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const [s, sc] = await Promise.all([
        getAdminStats(),
        getSchedulerStatus(),
      ]);
      setStats(s);
      setScheduler(sc);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "خطا در دریافت اطلاعات");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleRunScheduler = async () => {
    setSchedulerRunning(true);
    setSchedulerMsg("");
    try {
      const resp = await runScheduler();
      setSchedulerMsg(resp.message);
      const sc = await getSchedulerStatus();
      setScheduler(sc);
    } catch (err) {
      setSchedulerMsg(
        err instanceof Error ? err.message : "خطا در اجرای اسکجولر",
      );
    } finally {
      setSchedulerRunning(false);
    }
  };

  const handleClearCache = async () => {
    setCacheClearing(true);
    setCacheMsg("");
    try {
      const resp = await clearCache();
      setCacheMsg(resp.message);
      const s = await getAdminStats();
      setStats(s);
    } catch (err) {
      setCacheMsg(
        err instanceof Error ? err.message : "خطا در پاکسازی کش",
      );
    } finally {
      setCacheClearing(false);
    }
  };

  const formatSchedulerDate = (val: string | null) => {
    if (!val) return "—";
    const d = new Date(val);
    return d.toLocaleDateString("fa-IR", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div
      dir="rtl"
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 pt-12"
      onClick={onClose}
    >
      <div
        className="mx-4 w-full max-w-xl rounded-2xl bg-white shadow-xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-700">
          <h2 className="flex items-center gap-2 text-sm font-bold text-zinc-800 dark:text-zinc-200">
            <HiddenIcon><Activity size={16} /></HiddenIcon>
            پنل مدیریت
          </h2>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
            aria-label="بستن پنل مدیریت"
          >
            <HiddenIcon><X size={16} /></HiddenIcon>
          </button>
        </div>

        {/* body */}
        <div className="max-h-[70vh] overflow-y-auto px-4 pb-4">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-zinc-400">
              <Loader2 size={18} className="animate-spin" />
              در حال بارگذاری …
            </div>
          )}

          {errorMsg && (
            <div className="mt-3 flex items-center gap-1.5 rounded-lg bg-red-50 p-2.5 text-xs text-red-600 dark:bg-red-950 dark:text-red-400">
              <AlertCircle size={14} />
              {errorMsg}
            </div>
          )}

          {!loading && (
            <div className="mt-3 space-y-4">
              {/* Stats cards */}
              <section>
                <h3 className="mb-2 flex items-center gap-1.5 text-xs font-bold text-zinc-600 dark:text-zinc-400">
                  <HiddenIcon><Database size={13} /></HiddenIcon>
                  آمار سیستم
                </h3>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {(
                [
                  {
                    label: "قطعات برداری",
                    value: stats?.vector_store_count,
                    variant: "blue", // R-14: cards vary by metric importance; vector store is primary
                  },
                  {
                    label: "اسناد",
                    value: stats?.document_count,
                    variant: "green", // R-14: documents are secondary core metric
                  },
                  {
                    label: "کش Embedding",
                    value: stats?.cache_embedding_size,
                    variant: "amber", // R-14: cache metrics are tertiary
                  },
                  {
                    label: "کش LLM",
                    value: stats?.cache_llm_size,
                    variant: "purple", // R-14: cache metrics are tertiary
                  },
                  {
                    label: "کش RAG",
                    value: stats?.cache_rag_size,
                    variant: "zinc", // R-14: cache metrics are tertiary
                  },
                ] as const
                  ).map((item, i) => {
                    const variant = (() => {
                      switch (item.variant) {
                        case "blue":
                          return {
                            bg: "bg-blue-50",
                            border: "border-blue-200",
                            text: "text-blue-600",
                            labelColor: "text-blue-500",
                          };
                        case "green":
                          return {
                            bg: "bg-green-50",
                            border: "border-green-200",
                            text: "text-green-600",
                            labelColor: "text-green-500",
                          };
                        case "amber":
                          return {
                            bg: "bg-amber-50",
                            border: "border-amber-200",
                            text: "text-amber-600",
                            labelColor: "text-amber-500",
                          };
                        case "purple":
                          return {
                            bg: "bg-purple-50",
                            border: "border-purple-200",
                            text: "text-purple-600",
                            labelColor: "text-purple-500",
                          };
                        default:
                          return {
                            bg: "bg-zinc-50",
                            border: "border-zinc-200",
                            text: "text-zinc-600",
                            labelColor: "text-zinc-500",
                          };
                      }
                    })();
                    return (
                      <div
                        key={i}
                        className={`flex flex-col gap-1 rounded-xl border ${variant.border} ${variant.bg} p-3 dark:border-zinc-700 dark:bg-zinc-800`}
                      >
                        <span className={`text-[10px] ${variant.labelColor}`}>
                          {item.label}
                        </span>
                        <span className={`text-base font-bold ${variant.text}`}>
                          {item.value !== undefined && item.value >= 0
                            ? item.value.toLocaleString("fa-IR")
                            : "—"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Scheduler */}
              <section>
                <h3 className="mb-2 flex items-center gap-1.5 text-xs font-bold text-zinc-600 dark:text-zinc-400">
                  <HiddenIcon><Clock size={13} /></HiddenIcon>
                  اسکجولر
                </h3>
                <div className="rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-800">
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <span className="text-zinc-400">آخرین اجرا:</span>
                    <span className="text-zinc-700 dark:text-zinc-300">
                      {formatSchedulerDate(scheduler?.last_fetch ?? null)}
                    </span>
                    <span className="text-zinc-400">وضعیت:</span>
                    <span
                      className={
                        scheduler?.status === "success"
                          ? "text-green-600 dark:text-green-400"
                          : scheduler?.status === "failed"
                            ? "text-red-600 dark:text-red-400"
                            : "text-zinc-500"
                      }
                    >
                      {scheduler?.status === "success"
                        ? "موفق"
                        : scheduler?.status === "failed"
                          ? "ناموفق"
                          : scheduler?.status ?? "—"}
                    </span>
                    <span className="text-zinc-400">اسناد دریافت شده:</span>
                    <span className="text-zinc-700 dark:text-zinc-300">
                      {scheduler?.total_documents?.toLocaleString("fa-IR") ??
                        "—"}
                    </span>
                  </div>
                  {scheduler?.error_message && (
                    <div className="mt-2 rounded-lg bg-red-50 p-2 text-[10px] text-red-600 dark:bg-red-950 dark:text-red-400">
                      {scheduler.error_message}
                    </div>
                  )}
                  <div className="mt-3 flex items-center gap-2">
                    <button
                      onClick={handleRunScheduler}
                      disabled={schedulerRunning}
                      className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                    >
                      {schedulerRunning ? (
                        <HiddenIcon><Loader2 size={13} className="animate-spin" /></HiddenIcon>
                      ) : (
                        <HiddenIcon><Play size={13} /></HiddenIcon>
                      )}
                      اجرای دستی
                    </button>
                    {schedulerMsg && (
                      <span className="text-[10px] text-green-600 dark:text-green-400">
                        {schedulerMsg}
                      </span>
                    )}
                  </div>
                </div>
              </section>

              {/* Cache */}
              <section>
                <h3 className="mb-2 flex items-center gap-1.5 text-xs font-bold text-zinc-600 dark:text-zinc-400">
                  <HiddenIcon><Cpu size={13} /></HiddenIcon>
                  حافظه موقت (کش)
                </h3>
                <div className="rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-800">
                  <button
                    onClick={handleClearCache}
                    disabled={cacheClearing}
                    className="flex items-center gap-1.5 rounded-lg bg-red-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-600 disabled:opacity-50"
                  >
                    {cacheClearing ? (
                      <HiddenIcon><Loader2 size={13} className="animate-spin" /></HiddenIcon>
                    ) : (
                      <HiddenIcon><Trash2 size={13} /></HiddenIcon>
                    )}
                    پاکسازی همه کش‌ها
                  </button>
                  {cacheMsg && (
                    <div className="mt-2 flex items-center gap-1.5 text-[10px] text-green-600 dark:text-green-400">
                      <HiddenIcon><Check size={11} /></HiddenIcon>
                      {cacheMsg}
                    </div>
                  )}
                </div>
              </section>

              {/* refresh */}
              <div className="flex justify-center pb-2">
                <button
                  onClick={load}
                  className="flex items-center gap-1 text-[10px] text-zinc-400 hover:text-zinc-600"
                >
                  <HiddenIcon><RefreshCw size={11} /></HiddenIcon>
                  به‌روزرسانی
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


