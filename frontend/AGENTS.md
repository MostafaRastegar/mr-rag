# mr-rag Frontend – Agent Guide

## Project Context

- **mr-rag** is a Persian-aware RAG (Retrieval-Augmented Generation) system
- Backend: FastAPI at `http://127.0.0.1:8080` (configurable via `NEXT_PUBLIC_API_BASE`)
- Frontend: Next.js 16 + React 19 + Tailwind CSS 4

## Architecture

```
mr-rag-frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx      # Root layout: RTL, Vazirmatn font, Persian metadata
│   │   ├── page.tsx        # Entry point → renders ChatContainer
│   │   └── globals.css     # Tailwind imports + CSS custom properties
│   ├── components/
│   │   ├── ChatContainer.tsx  # Main orchestration: health check, send, stream, state
│   │   ├── ChatInput.tsx      # RTL textarea with Enter-to-send, auto-resize
│   │   └── MessageBubble.tsx  # User/assistant bubbles with collapsible sources
│   └── lib/
│       └── api.ts             # Typed API client (chat, stream, health, ingest)
├── next.config.ts
├── package.json
└── tsconfig.json
```

## Data Flow

```
User types question
   → ChatInput.onSend(question)
   → ChatContainer.handleSend()
       → [adds user message to state]
       → [adds empty assistant message with streaming=true]
       → chatStream(question) — yields tokens progressively
           → updates assistant message text in real-time
       → sendChat(question) — after stream completes, fetches sources
           → updates assistant message with final text + sources, streaming=false
   → MessageBubble renders:
       - streaming: pulsating cursor
       - sources: collapsible accordion with score badges
```

## Key Conventions

### RTL (Right-to-Left)

- `<html dir="rtl" lang="fa">` in layout.tsx
- Every form/container uses `dir="rtl"`
- Text alignment and flex direction are RTL-native

### Persian Text

- All labels, placeholders, and messages are in Persian
- Font: **Vazirmatn** loaded via `next/font/google`
- CSS variable: `--font-vazir`
- Fallback stack: `var(--font-vazir), "Vazirmatn", "Tahoma", system-ui, sans-serif`

### API Handling

- Streaming first, then full response for sources
- If streaming fails but partial text exists, keep what we got
- AbortController for cancellation
- Health check every 30s with visual badge

### State Management

- No external state library — React `useState` + `useCallback`
- Messages array with `Message` interface:
  ```ts
  interface Message {
    id: string;
    role: "user" | "assistant";
    text: string;
    sources?: SourceItem[];
    streaming?: boolean;
  }
  ```

### Error Handling

- Network errors → Persian error message in chat
- Health check failures → red "قطع" badge
- AbortError silently ignored (user cancelled mid-stream)

## How to Add a Feature

### New API Endpoint

1. Add function in `src/lib/api.ts` with typed response
2. Call it from `ChatContainer.tsx` (or a new component)

### New Component

1. Create in `src/components/`
2. Use `"use client"` directive if it uses hooks/state
3. Import via `@/components/YourComponent`

### Environment Variable

- Public: prefix with `NEXT_PUBLIC_` (e.g. `NEXT_PUBLIC_API_BASE`)
- Private: add to `next.config.ts` env block
