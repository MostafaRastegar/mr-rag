"use client";

import { useEffect, useState } from "react";
import {
  MessageSquare,
  Plus,
  Trash2,
  PanelLeftClose,
  PanelLeft,
  Clock,
} from "lucide-react";
import type { Conversation } from "@/lib/db";
import { getAllConversations, deleteConversation } from "@/lib/db";

interface SidebarProps {
  activeConversationId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  open: boolean;
  onToggle: () => void;
  refreshTrigger: number;
}

export default function Sidebar({
  activeConversationId,
  onSelect,
  onNew,
  open,
  onToggle,
  refreshTrigger,
}: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);

  /* load list on mount, when sidebar opens, or when refreshTrigger changes */
  useEffect(() => {
    getAllConversations().then(setConversations);
  }, [open, refreshTrigger]);

  /* refresh list after a new conversation is created */
  const refresh = () => getAllConversations().then(setConversations);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await deleteConversation(id);
    refresh();
  };

  const handleNew = () => {
    onNew();
    refresh();
  };

  const formatDate = (ts: number) => {
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60_000);

    if (diffMin < 1) return "همین الان";
    if (diffMin < 60) return `${diffMin} دقیقه پیش`;

    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} ساعت پیش`;

    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 7) return `${diffDay} روز پیش`;

    return d.toLocaleDateString("fa-IR", {
      month: "short",
      day: "numeric",
    });
  };

  return (
    <>
      {/* toggle button (always visible) */}
      <button
        onClick={onToggle}
        className="fixed right-2 top-3 z-50 flex h-8 w-8 items-center justify-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-200 hover:text-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
        title={open ? "بستن منو" : "نمایش تاریخچه"}
      >
        {open ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
      </button>

      {/* overlay on mobile */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/20 md:hidden"
          onClick={onToggle}
        />
      )}

      {/* sidebar panel */}
      <aside
        dir="rtl"
        className={`fixed right-0 top-0 z-40 flex h-dvh w-72 flex-col border-l border-zinc-200 bg-white transition-transform duration-200 dark:border-zinc-700 dark:bg-zinc-900 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-700">
          <h2 className="text-sm font-bold text-zinc-800 dark:text-zinc-200">
            تاریخچه مکالمات
          </h2>
          <button
            onClick={handleNew}
            className="flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700"
          >
            <Plus size={14} />
            جدید
          </button>
        </div>

        {/* conversation list */}
        <div className="flex-1 overflow-y-auto p-2">
          {conversations.length === 0 ? (
            <p className="mt-8 text-center text-xs text-zinc-400">
              هیچ مکالمه‌ای وجود ندارد
            </p>
          ) : (
            <ul className="space-y-1">
              {conversations.map((conv) => (
                <li
                  key={conv.id}
                  onClick={() => onSelect(conv.id)}
                  className={`group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2.5 text-xs transition-colors ${
                    conv.id === activeConversationId
                      ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                      : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  }`}
                >
                  <MessageSquare size={14} className="shrink-0 opacity-50" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">
                      {conv.title || "مکالمه جدید"}
                    </p>
                    <p className="mt-0.5 flex items-center gap-1 text-[10px] opacity-50">
                      <Clock size={10} />
                      {formatDate(conv.updatedAt)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, conv.id)}
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-zinc-400 opacity-0 transition-opacity hover:bg-red-100 hover:text-red-500 group-hover:opacity-100"
                    title="حذف"
                  >
                    <Trash2 size={13} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </>
  );
}
