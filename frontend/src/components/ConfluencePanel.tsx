"use client";

import { useState } from "react";
import {
  X,
  Loader2,
  AlertCircle,
  CheckCircle,
  Play,
  RefreshCw,
  Database,
  Link,
} from "lucide-react";

/* آیکون‌های تزئینی lucide (R-39) */
const HiddenIcon = ({ children }: { children: React.ReactNode }) => (
  <span aria-hidden="true">{children}</span>
);

import {
  testConfluence,
  getConfluenceSpaces,
  getConfluencePages,
  indexConfluence,
  syncConfluence,
  getConfluenceStatus,
} from "@/lib/api";
import type {
  ConfluenceCreds,
  ConfluenceIndexRequest,
  ConfluenceIndexResponse,
  ConfluencePageItem,
  ConfluenceSpaceItem,
  ConfluenceSpacesResponse,
  ConfluenceStatusResponse,
} from "@/lib/api";

interface ConfluencePanelProps {
  onClose: () => void;
}

type AuthType = "bearer" | "basic";
type IndexMode = "ids" | "space" | "subtree";

type Status = "idle" | "testing" | "listing" | "indexing" | "done" | "error";

export default function ConfluencePanel({ onClose }: ConfluencePanelProps) {
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  /* connection form */
  const [baseUrl, setBaseUrl] = useState("");
  const [authType, setAuthType] = useState<AuthType>("bearer");
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");

  /* discovered data */
  const [spaces, setSpaces] = useState<ConfluenceSpaceItem[]>([]);
  const [pages, setPages] = useState<ConfluencePageItem[]>([]);
  const [selectedPageIds, setSelectedPageIds] = useState<Set<string>>(new Set());

  /* index mode */
  const [mode, setMode] = useState<IndexMode>("space");
  const [spaceKey, setSpaceKey] = useState("");
  const [rootPageId, setRootPageId] = useState("");
  const [recursive, setRecursive] = useState(false);
  const [pageIdsText, setPageIdsText] = useState("");

  /* results */
  const [result, setResult] = useState<ConfluenceIndexResponse | null>(null);
  const [syncStatus, setSyncStatus] = useState<ConfluenceStatusResponse | null>(
    null,
  );

  const creds: ConfluenceCreds = {
    base_url: baseUrl.trim(),
    auth_type: authType,
    token: token.trim(),
    email: email.trim() || undefined,
    username: username.trim() || undefined,
  };

  const handleTest = async () => {
    setStatus("testing");
    setErrorMsg("");
    try {
      const resp = await testConfluence(creds);
      setStatus("done");
      setErrorMsg(
        `اتصال موفق — کاربر: ${resp.user || "—"}، فضاها: ${resp.spaces_count ?? 0}`,
      );
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "خطا در تست اتصال کانفلوئنس",
      );
    }
  };

  const handleLoadSpaces = async () => {
    setStatus("listing");
    setErrorMsg("");
    try {
      const resp = await getConfluenceSpaces({ ...creds, limit: 100 });
      setSpaces(resp.spaces);
      setStatus("done");
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "خطا در دریافت فضاها",
      );
    }
  };

  const handleLoadPages = async () => {
    setStatus("listing");
    setErrorMsg("");
    try {
      const resp = await getConfluencePages({
        ...creds,
        space_key: mode === "space" ? spaceKey : undefined,
        parent_page_id: mode === "subtree" ? rootPageId : undefined,
        limit: 100,
      });
      setPages(resp.pages);
      setStatus("done");
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "خطا در دریافت صفحات");
    }
  };

  const handleIndex = async () => {
    setStatus("indexing");
    setErrorMsg("");
    setResult(null);

    const request: ConfluenceIndexRequest = {
      ...creds,
      mode,
      page_ids:
        mode === "ids"
          ? pageIdsText
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : undefined,
      space_key: mode === "space" ? spaceKey : undefined,
      root_page_id: mode === "subtree" ? rootPageId : undefined,
      recursive: mode === "subtree" ? recursive : false,
    };

    try {
      const resp = await indexConfluence(request);
      setResult(resp);
      setStatus("done");
      setErrorMsg(
        `${resp.pages_indexed} صفحه اندیس شد، ${resp.pages_failed} شکست، ${resp.chunks_ingested} قطعه`,
      );
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error ? err.message : "خطا در اندیس‌سازی کانفلوئنس",
      );
    }
  };

  const handleSync = async () => {
    setStatus("indexing");
    setErrorMsg("");
    try {
      const resp = await syncConfluence(requestFromState());
      setResult(resp);
      setStatus("done");
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "خطا در هم‌زمانی");
    }
  };

  const requestFromState = (): ConfluenceIndexRequest => ({
    ...creds,
    mode,
    page_ids:
      mode === "ids"
        ? pageIdsText.split(",").map((s) => s.trim()).filter(Boolean)
        : undefined,
    space_key: mode === "space" ? spaceKey : undefined,
    root_page_id: mode === "subtree" ? rootPageId : undefined,
    recursive: mode === "subtree" ? recursive : false,
  });

  const handleLoadStatus = async () => {
    try {
      const s = await getConfluenceStatus();
      setSyncStatus(s);
    } catch {
      /* status is best-effort */
    }
  };

  const togglePage = (id: string) => {
    setSelectedPageIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const isSelected = (id: string) => selectedPageIds.has(id);

  return (
    <div
      dir="rtl"
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 pt-12"
      onClick={onClose}
    >
      <div
        className="mx-4 w-full max-w-3xl rounded-2xl bg-white shadow-xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-700">
          <h2 className="flex items-center gap-2 text-sm font-bold text-zinc-800 dark:text-zinc-200">
            <HiddenIcon><Database size={16} /></HiddenIcon>
            اتصال به کانفلوئنس
          </h2>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
            aria-label="بستن پنل کانفلوئنس"
          >
            <HiddenIcon><X size={16} /></HiddenIcon>
          </button>
        </div>

        <div className="p-4 space-y-3">
          {/* connection form */}
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-zinc-500">آدرس کانفلوئنس</label>
                <input
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://confluence.sazeman.ir"
                  className="rounded border border-zinc-300 px-2 py-1.5 text-xs focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-zinc-500">نوع احراز هویت</label>
                <select
                  value={authType}
                  onChange={(e) => setAuthType(e.target.value as AuthType)}
                  className="rounded border border-zinc-300 px-2 py-1.5 text-xs focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                >
                  <option value="bearer">توکن شخصی (Bearer)</option>
                  <option value="basic">کانفلوئنس کلود (ایمیل + توکن)</option>
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-zinc-500">توکن / API Token</label>
                <input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  className="rounded border border-zinc-300 px-2 py-1.5 text-xs focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                />
              </div>
              {authType === "basic" && (
                <>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-zinc-500">ایمیل</label>
                    <input
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="rounded border border-zinc-300 px-2 py-1.5 text-xs focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-zinc-500">نام کاربری (اختیاری)</label>
                    <input
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="rounded border border-zinc-300 px-2 py-1.5 text-xs focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                    />
                  </div>
                </>
              )}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <button
                onClick={handleTest}
                disabled={status === "testing"}
                className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors disabled:opacity-50 hover:bg-blue-700"
              >
                {status === "testing" ? (
                  <HiddenIcon><Loader2 size={14} className="animate-spin" /></HiddenIcon>
                ) : (
                  <HiddenIcon><Play size={14} /></HiddenIcon>
                )}
                تست اتصال
              </button>
              <button
                onClick={handleLoadStatus}
                className="flex items-center gap-1.5 rounded-lg border border-zinc-300 px-2 py-1.5 text-xs text-zinc-600 hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                <HiddenIcon><RefreshCw size={14} /></HiddenIcon>
                وضعیت آخرین هم‌زمانی
              </button>
            </div>
            {errorMsg && status === "error" && (
              <div className="mt-2 flex items-center gap-1 rounded-lg bg-red-50 p-1.5 text-xs text-red-600 dark:bg-red-950 dark:text-red-400">
                <AlertCircle size={12} /> {errorMsg}
              </div>
            )}
            {errorMsg && status === "done" && (
              <div className="mt-2 flex items-center gap-1 rounded-lg bg-green-50 p-1.5 text-xs text-green-600 dark:bg-green-950 dark:text-green-400">
                <CheckCircle size={12} /> {errorMsg}
              </div>
            )}
          </div>

          {/* page selection */}
          <div className="rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-800">
            <div className="flex items-center gap-2 mb-2">
              <label className="text-xs font-medium text-zinc-500">روش انتخاب صفحات</label>
              <div className="flex gap-1 rounded-lg border border-zinc-300 dark:border-zinc-600">
                <button
                  key="ids"
                  onClick={() => setMode("ids")}
                  className={`px-2 py-1 text-xs rounded-md transition-colors ${
                    mode === "ids"
                      ? "bg-blue-600 text-white"
                      : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  }`}
                >
                  آی‌دی صفحات
                </button>
                <button
                  key="space"
                  onClick={() => setMode("space")}
                  className={`px-2 py-1 text-xs rounded-md transition-colors ${
                    mode === "space"
                      ? "bg-blue-600 text-white"
                      : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  }`}
                >
                  کل فضا
                </button>
                <button
                  key="subtree"
                  onClick={() => setMode("subtree")}
                  className={`px-2 py-1 text-xs rounded-md transition-colors ${
                    mode === "subtree"
                      ? "bg-blue-600 text-white"
                      : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  }`}
                >
                  زیردرخت
                </button>
              </div>
            </div>

            {mode === "ids" && (
              <div className="flex flex-col gap-1">
                <label className="text-xs text-zinc-500">آی‌دی صفحات (با کاما جدا شده)</label>
                <input
                  value={pageIdsText}
                  onChange={(e) => setPageIdsText(e.target.value)}
                  placeholder="1001, 1002, 1003"
                  className="rounded border border-zinc-300 px-2 py-1.5 text-xs focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                />
              </div>
            )}

            {mode === "space" && (
              <div className="flex flex-col gap-1">
                <label className="text-xs text-zinc-500">کلید فضا</label>
                <select
                  value={spaceKey}
                  onChange={(e) => setSpaceKey(e.target.value)}
                  className="rounded border border-zinc-300 px-2 py-1.5 text-xs focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                >
                  <option value="">انتخاب فضا…</option>
                  {spaces.map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.name} ({s.key})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {mode === "subtree" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-zinc-500">صفحه ریشه</label>
                  <input
                    value={rootPageId}
                    onChange={(e) => setRootPageId(e.target.value)}
                    placeholder="1001"
                    className="rounded border border-zinc-300 px-2 py-1.5 text-xs focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                  />
                </div>
                <div className="flex items-end gap-2">
                  <input
                    id="recursive"
                    type="checkbox"
                    checked={recursive}
                    onChange={() => setRecursive(!recursive)}
                    className="rounded border-zinc-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700"
                  />
                  <label htmlFor="recursive" className="text-xs text-zinc-600 dark:text-zinc-300">
                    כולل صفحات زیرمجموعه (بازчено)
                  </label>
                </div>
              </div>
            )}

            {pages.length > 0 && (
              <div className="mt-3 max-h-48 overflow-y-auto border border-zinc-200 rounded-lg p-2 text-xs dark:border-zinc-700 dark:bg-zinc-800">
                {pages.map((p) => (
                  <div
                    key={p.id}
                    className="flex items-center gap-2 cursor-pointer rounded px-2 py-1 hover:bg-zinc-100 dark:hover:bg-zinc-700"
                    onClick={() => togglePage(p.id)}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected(p.id)}
                      readOnly
                      onChange={(e) => e.preventDefault()}
                      className="rounded border-zinc-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700"
                    />
                    <span className="truncate">
                      {p.title}
                      <span className="ml-1 text-[10px] opacity-60">({p.space_key})</span>
                    </span>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-2 flex items-center gap-2">
              <button
                onClick={handleLoadPages}
                disabled={status === "listing" || mode === "ids"}
                className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 hover:bg-blue-700"
              >
                {status === "listing" ? (
                  <HiddenIcon><Loader2 size={14} className="animate-spin" /></HiddenIcon>
                ) : (
                  <HiddenIcon><RefreshCw size={14} /></HiddenIcon>
                )}
                بارگذاری صفحات
              </button>
              <button
                onClick={handleIndex}
                disabled={status === "indexing"}
                className="flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 hover:bg-green-700"
              >
                {status === "indexing" ? (
                  <HiddenIcon><Loader2 size={14} className="animate-spin" /></HiddenIcon>
                ) : (
                  <HiddenIcon><Play size={14} /></HiddenIcon>
                )}
                اندیس‌سازی избран Pages
              </button>
              <button
                onClick={handleSync}
                className="flex items-center gap-1.5 rounded-lg border border-zinc-300 px-2 py-1.5 text-xs text-zinc-600 hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                هم‌زمانی مجدد
              </button>
            </div>
          </div>

          {/* result */}
          {result && (
            <div className="rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-800">
              <div className="flex items-center gap-2 text-xs font-medium text-zinc-500 mb-1">
                <HiddenIcon><CheckCircle size={14} /></HiddenIcon>
                نتیجه اندیس‌سازی
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                <div className="bg-zinc-100 p-2 rounded dark:bg-zinc-800">
                  <div className="text-[10px] text-zinc-500">صفحه اندیس شده</div>
                  <div className="font-bold">{result.pages_indexed}</div>
                </div>
                <div className="bg-zinc-100 p-2 rounded dark:bg-zinc-800">
                  <div className="text-[10px] text-zinc-500">شکست خوردה</div>
                  <div className="font-bold text-red-600">{result.pages_failed}</div>
                </div>
                <div className="bg-zinc-100 p-2 rounded dark:bg-zinc-800">
                  <div className="text-[10px] text-zinc-500">قطعه ذخیره شده</div>
                  <div className="font-bold">{result.chunks_ingested}</div>
                </div>
              </div>
              {result.errors.length > 0 && (
                <div className="mt-2 max-h-32 overflow-y-auto text-xs text-red-600 dark:text-red-400">
                  {result.errors.map((e) => (
                    <div key={e.page_id} className="mb-1 truncate">
                      {e.page_title || e.page_id}: {e.error}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* last sync status */}
          {syncStatus && syncStatus.pages_indexed !== null && (
            <div className="text-xs text-zinc-500 mt-2">
              آخرین هم‌زمانی: {syncStatus.pages_indexed} صفحه، {syncStatus.chunks_ingested} قطعه
              {syncStatus.error ? ` — خطا: ${syncStatus.error}` : ""}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
