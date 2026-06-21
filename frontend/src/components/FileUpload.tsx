"use client";

import { useState, useRef, type DragEvent, type ChangeEvent } from "react";
import { Upload, File, X, Loader2, Check, AlertCircle } from "lucide-react";
import { uploadFile } from "@/lib/api";
import type { UploadResponse } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface UploadResult {
  fileName: string;
  chunks: number;
  message: string;
}

type Status = "idle" | "dragging" | "uploading" | "success" | "error";

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

interface FileUploadProps {
  onSuccess: (result: UploadResult) => void;
  onClose: () => void;
}

const ALLOWED_EXTENSIONS = [".json", ".md", ".txt"];

export default function FileUpload({ onSuccess, onClose }: FileUploadProps) {
  const [status, setStatus] = useState<Status>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const isValidFile = (f: File) => {
    const ext = "." + f.name.split(".").pop()?.toLowerCase();
    return ALLOWED_EXTENSIONS.includes(ext);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f && isValidFile(f)) {
      setFile(f);
      setStatus("idle");
      setErrorMsg("");
    } else {
      setErrorMsg("فایل‌های JSON، MD یا TXT مجاز هستند");
      setStatus("idle");
    }
  };

  const handleSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      if (isValidFile(f)) {
        setFile(f);
        setStatus("idle");
        setErrorMsg("");
      } else {
        setErrorMsg("فایل‌های JSON، MD یا TXT مجاز هستند");
        setStatus("idle");
      }
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setStatus("uploading");
    try {
      const resp: UploadResponse = await uploadFile(file);
      setStatus("success");
      onSuccess({
        fileName: resp.file_name,
        chunks: resp.chunks_ingested,
        message: resp.message,
      });
      // auto-close after 2s
      setTimeout(onClose, 2000);
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "خطا در آپلود");
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */

  return (
    <div
      dir="rtl"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      onClick={onClose}
    >
      <div
        className="mx-4 w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-zinc-800 dark:text-zinc-200">
            بارگذاری سند
          </h2>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
          >
            <X size={16} />
          </button>
        </div>

        {/* drag zone */}
        {status !== "success" && (
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onDragEnter={() => setStatus("dragging")}
            onDragLeave={() => setStatus("idle")}
            onClick={() => inputRef.current?.click()}
            className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-colors ${
              status === "dragging"
                ? "border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950"
                : "border-zinc-300 hover:border-zinc-400 dark:border-zinc-600 dark:hover:border-zinc-500"
            }`}
          >
            <Upload
              size={32}
              className={
                status === "dragging" ? "text-blue-500" : "text-zinc-400"
              }
            />
            <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
              فایل را اینجا رها کنید یا کلیک کنید
            </p>
            <p className="mt-1 text-[10px] text-zinc-400">JSON ‌• MD ‌• TXT</p>
            <input
              ref={inputRef}
              type="file"
              accept=".json,.md,.txt"
              className="hidden"
              onChange={handleSelect}
            />
          </div>
        )}

        {/* selected file info */}
        {file && status !== "success" && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-800">
            <File size={16} className="shrink-0 text-blue-500" />
            <span className="flex-1 truncate font-medium text-zinc-700 dark:text-zinc-300">
              {file.name}
            </span>
            <span className="text-zinc-400">
              {(file.size / 1024).toFixed(1)} KB
            </span>
          </div>
        )}

        {/* error */}
        {errorMsg && (
          <div className="mt-3 flex items-center gap-1.5 rounded-lg bg-red-50 p-2.5 text-xs text-red-600 dark:bg-red-950 dark:text-red-400">
            <AlertCircle size={14} />
            {errorMsg}
          </div>
        )}

        {/* success */}
        {status === "success" && (
          <div className="mt-4 flex flex-col items-center gap-2 rounded-xl bg-green-50 p-6 dark:bg-green-950">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
              <Check size={24} className="text-green-600 dark:text-green-400" />
            </div>
            <p className="text-sm font-medium text-green-700 dark:text-green-300">
              بارگذاری موفق
            </p>
          </div>
        )}

        {/* actions */}
        <div className="mt-4 flex gap-2">
          {status !== "success" && (
            <>
              <button
                onClick={handleUpload}
                disabled={!file || status === "uploading"}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
              >
                {status === "uploading" ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    در حال بارگذاری …
                  </>
                ) : (
                  <>
                    <Upload size={16} />
                    بارگذاری
                  </>
                )}
              </button>
              <button
                onClick={onClose}
                disabled={status === "uploading"}
                className="rounded-xl border border-zinc-300 px-4 py-2.5 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-50 dark:border-zinc-600 dark:text-zinc-400 dark:hover:bg-zinc-800"
              >
                انصراف
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
