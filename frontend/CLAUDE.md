# mr-rag Frontend — Development Guide

## Commands

```bash
# Development
npm run dev          # Start dev server (http://localhost:3000)

# Build
npm run build        # Production build
npm run start        # Start production server

# Lint
npm run lint         # ESLint
```

## Tech Stack

| Layer      | Choice                       |
| ---------- | ---------------------------- |
| Framework  | Next.js 16 (App Router)      |
| UI Library | React 19                     |
| Styling    | Tailwind CSS 4               |
| Icons      | Lucide React                 |
| Font       | Vazirmatn (next/font/google) |

## Project Structure

```
src/
├── app/          # Next.js App Router (layout, page, globals.css)
├── components/   # Client components (ChatContainer, ChatInput, MessageBubble)
└── lib/          # API client utilities
```

## Key Patterns

### 1. All Client Components use `"use client"` directive

```tsx
"use client";
import { useState } from "react";
```

### 2. API client uses typed functions, not classes

```ts
// src/lib/api.ts
export async function sendChat(question: string): Promise<ChatResponse>
export async function* chatStream(question: string): AsyncGenerator<string>
export async function getHealth(): Promise<HealthResponse>
```

### 3. Streaming with AsyncGenerator

```ts
for await (const token of chatStream(question)) {
  // append token to message text
}
```

### 4. Environment Variables

| Variable               | Default                 | Description     |
| ---------------------- | ----------------------- | --------------- |
| `NEXT_PUBLIC_API_BASE` | `http://127.0.0.1:8080` | Backend API URL |

Copy `.env.example` → `.env.local` to override.

## API Endpoints (Backend)

| Method | Endpoint       | Body            | Response                         |
| ------ | -------------- | --------------- | -------------------------------- |
| GET    | `/health`      | —               | `{ status, vector_store_count }` |
| POST   | `/chat`        | `{ question }`  | `{ answer, sources[] }`          |
| POST   | `/chat/stream` | `{ question }`  | SSE text stream                  |
| POST   | `/ingest`      | `{ file_path }` | `{ status, chunks_ingested }`    |
