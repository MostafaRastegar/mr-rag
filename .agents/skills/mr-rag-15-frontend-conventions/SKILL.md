---
name: mr-rag-15-frontend-conventions
description: Next.js 16 + React 19 + Tailwind CSS 4 frontend coding patterns
---

# mr-rag-15-frontend-conventions

## Usage

Use this skill when creating or modifying frontend code to ensure consistency with established project conventions.

## File Structure

```
src/
├── app/             # Next.js App Router (layout.tsx, page.tsx, globals.css)
├── components/      # All React components (flat, no subdirectories)
└── lib/             # Pure TypeScript utilities (api.ts, db.ts)
```

## Component File Template

```tsx
"use client";

import { useState, useEffect } from "react";
import { X, Loader2, AlertCircle } from "lucide-react";
import { someApi } from "@/lib/api";
import type { SomeType } from "@/lib/api";

interface ComponentNameProps {
  onClose: () => void;
}

type Status = "loading" | "loaded" | "error";

export default function ComponentName({ onClose }: ComponentNameProps) {
  // state
  // effects
  // handlers

  return (
    <div dir="rtl">…</div>
  );
}
```

## Import Order

1. React hooks: `import { useState, useEffect, useCallback, useRef } from "react"`
2. Icons from lucide-react: `import { X, Loader2 } from "lucide-react"`
3. Local components: `import ComponentName from "./ComponentName"`
4. Component types: `import type { Message } from "./MessageBubble"`
5. Library imports: `import { apiFunction } from "@/lib/api"`
6. Library types: `import type { ResponseType } from "@/lib/api"`

Groups separated by blank lines. Type imports use `import type { ... }`.

## Component Patterns

- `"use client"` on line 1 for ALL components using hooks/state
- `export default function ComponentName()` — no `React.FC`, no arrow functions
- Props interface named `ComponentNameProps`, defined immediately before the component
- Exported interfaces for shared types (e.g. `export interface Message { ... }`)
- Status union type for multi-state components: `type Status = "idle" | "loading" | "success" | "error"`

## Modal Pattern

```tsx
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
        <Icon size={16} />
        عنوان
      </h2>
      <button
        onClick={onClose}
        className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
      >
        <X size={16} />
      </button>
    </div>
    {/* body */}
    <div className="max-h-[70vh] overflow-y-auto px-4 pb-4">…</div>
  </div>
</div>
```

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Component files | PascalCase | `ChatContainer.tsx`, `AdminPanel.tsx` |
| Lib files | camelCase | `api.ts`, `db.ts` |
| Component exports | PascalCase, default | `export default function ChatContainer()` |
| Props interfaces | PascalCase + `Props` | `AdminPanelProps`, `ChatInputProps` |
| Data interfaces | PascalCase + `Response`/`Item` | `DocumentListResponse`, `DocumentItem` |
| API functions | camelCase, verb-first | `getDocuments`, `createConversation` |
| Handlers | `handle` + Action | `handleSubmit`, `handleDelete` |
| Status types | PascalCase union | `type Status = "idle" \| "loading"` |
| State booleans | adjective/verb | `loading`, `showUpload`, `sidebarOpen` |
| Refs | camelCase + `Ref` | `bottomRef`, `abortRef` |

## Tailwind CSS Conventions

### Zinc Color Palette

- Surfaces: `bg-white` / `dark:bg-zinc-900`
- Secondary surfaces: `bg-zinc-100` / `dark:bg-zinc-800`
- Tertiary: `bg-zinc-50` / `dark:bg-zinc-800`
- Borders: `border-zinc-200` / `dark:border-zinc-700`
- Primary text: `text-zinc-900` / `dark:text-zinc-100`
- Secondary text: `text-zinc-800` / `dark:text-zinc-200`
- Muted text: `text-zinc-500` / `dark:text-zinc-400`
- Placeholders: `placeholder:text-zinc-400` / `dark:placeholder:text-zinc-500`

### Accent Colors

- **Blue** (primary actions, links): `bg-blue-600`, `bg-blue-50`, `text-blue-500`, `hover:bg-blue-700`
- **Red** (danger, errors, stop): `bg-red-500`, `bg-red-50`, `text-red-500`, `hover:bg-red-600`
- **Green** (success, health): `bg-green-50`, `text-green-600` / `dark:text-green-400`
- **Amber** (JSON file badges): `bg-amber-100 text-amber-700` / `dark:bg-amber-900 dark:text-amber-300`

### Border Radius

- `rounded-lg` — buttons, badges, file info cards
- `rounded-xl` — textareas, modals, document list items
- `rounded-2xl` — chat bubbles, modals
- `rounded-md` — file type badges
- `rounded-full` — health dots, circles

### Button Styles

**Primary (blue):**
```
flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50
```

**Secondary (zinc):**
```
flex items-center gap-1.5 rounded-lg bg-zinc-100 px-4 py-2 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700
```

**Danger (red):**
```
flex items-center gap-1.5 rounded-lg bg-red-500 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-red-600 disabled:opacity-50
```

**Toolbar header button:**
```
flex h-7 items-center gap-1 rounded-lg bg-zinc-100 px-2.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700
```

**Icon-only (close):**
```
flex h-7 w-7 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800
```

### Input/Textarea Pattern

```
rounded-xl border border-zinc-300 bg-zinc-50 px-4 py-3 text-sm
text-zinc-900 placeholder:text-zinc-400
focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500
disabled:opacity-50
dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:placeholder:text-zinc-500
```

### Error Banner

```
mt-3 flex items-center gap-1.5 rounded-lg bg-red-50 p-2.5 text-xs text-red-600 dark:bg-red-950 dark:text-red-400
```

### Loading Spinner

```
flex items-center justify-center gap-2 py-12 text-sm text-zinc-400
```

### Empty State

```
flex flex-col items-center gap-2 py-12
```

### List Items

```
rounded-xl border border-zinc-200 bg-white p-3 text-xs dark:border-zinc-700 dark:bg-zinc-800
```

### Font Sizes

- `text-[10px]` — captions, metadata, timestamps, file type badges
- `text-xs` — panel body text, buttons, labels
- `text-sm` — main body text, chat bubbles, input text, section headers
- `text-base` — stat values
- `text-lg` — header titles

### Font Weights

- `font-bold` — titles, section headers, stat values
- `font-medium` — buttons, conversation titles, file names
- `font-semibold` — role labels

## API Layer Pattern

```tsx
export async function functionName(params): Promise<ResponseType> {
  const res = await fetch(`${API_BASE}/endpoint/${encodeURIComponent(id)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: value }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Description (${res.status}): ${err}`);
  }
  return res.json();
}
```

- `API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8080"`
- `encodeURIComponent()` for all path parameter IDs
- All response types `export interface` in the same file
- `res.text()` for error messages, then `throw new Error()`
- `return res.json()` or `return res.text()` for metrics

## State Management Patterns

```tsx
// Status union (preferred for complex states)
type Status = "idle" | "loading" | "loaded" | "error";
const [status, setStatus] = useState<Status>("idle");

// Boolean for simple flags
const [showModal, setShowModal] = useState(false);

// Nullable data
const [data, setData] = useState<ResponseType | null>(null);

// Refs
const bottomRef = useRef<HTMLDivElement>(null);          // DOM ref
const abortRef = useRef<AbortController | null>(null);   // cancellation
const valRef = useRef(value);                            // mutable latest value

// useCallback for all handlers passed as props
const handleAction = useCallback(async () => { ... }, [deps]);

// Debounced effect with cleanup
useEffect(() => {
  if (timerRef.current) clearTimeout(timerRef.current);
  timerRef.current = setTimeout(() => { ... }, 500);
  return () => { if (timerRef.current) clearTimeout(timerRef.current); };
}, [deps]);
```

## RTL & Persian Conventions

- Every component wrap: `dir="rtl"`
- Root layout: `<html lang="fa" dir="rtl">`
- Font: `Vazirmatn` via `next/font/google`, CSS var `--font-vazir`
- All user-facing text in Persian (hardcoded, no i18n library)
- Date formatting: `toLocaleDateString("fa-IR", { ... })`
- Number formatting: `toLocaleString("fa-IR")`

## Section Comment Separators

Use dashed-line comment blocks for logical sections:

```tsx
/* ------------------------------------------------------------------ */
/*  Section Name                                                       */
/* ------------------------------------------------------------------ */
```

## Should / Should Not

✅ Do: Use `"use client"` on line 1 for any component with hooks
✅ Do: Use `dark:` variants on EVERY styling class
✅ Do: Use `transition-colors` on all interactive elements
✅ Do: Use `type` for Status unions and `interface` for Props/data types
✅ Do: Use `import type { ... }` for type-only imports
✅ Do: Hardcode all UI text in Persian
✅ Do: Use `err instanceof Error ? err.message : "پیام خطا"` for error messages
❌ Don't: Use `React.FC` or arrow function components
❌ Don't: Create subdirectories under `components/`
❌ Don't: Use CSS modules or styled-components (pure Tailwind)
❌ Don't: Use i18n libraries
❌ Don't: Use `any` type — prefer `unknown` or specific types
❌ Don't: Use `tailwind.config.ts` (Tailwind v4 uses `@theme inline` in CSS)
❌ Don't: Forget `dir="rtl"` on form/container elements
