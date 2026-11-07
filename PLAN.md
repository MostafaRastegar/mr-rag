# Plan: Confluence Integration + Docker Test Stack (mr-rag)

## Goal

User supplies a Confluence personal key/token; the app indexes all specified pages (manual IDs / subtree / whole space), stores them in ChromaDB, and runs RAG over them. Entire stack comes up via Docker with mock Confluence test data and end-to-end RAG verification.

## Decisions (from user)

- Confluence type: both Server/DC (PAT bearer) and Cloud (email + API token basic).
- Token storage: session-only, never persisted; endpoints are POST (token never in URL/logs).
- Docker: full stack + mock Confluence under `--profile test`.
- Page selection: all three modes (manual page IDs, subtree/recursive, whole space).
- Auth detection: `.atlassian.net` → Cloud basic / `/wiki/rest/api`; else `/rest/api` bearer (overridable).

## Reuse strategy (ponytail)

- No new abstractions: reuse `IngestionPipeline`, ports, `VectorStorePort.delete_by_metadata`, `ChromaVectorStore`, `OpenRouterEmbedding`, `LangChainTextSplitter`, `SchedulerSettings`-style pydantic config, scheduler client/auth retry pattern.
- Add minimal shared core: `IngestionPipeline.run_documents(documents)` so Confluence doesn't need temp files.
- No Confluence SDK — raw `httpx` REST (already a dependency).

---

## New files

| Path                                          | Purpose                                                                                              |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `app/infrastructure/confluence_client.py`     | httpx REST client: auth, pagination, retry/backoff, HTML→text, page→document dict                    |
| `app/pipeline/confluence_ingestion.py`        | `ConfluenceIngestionService`: idempotent index (delete-by-page_id then add) for manual/subtree/space |
| `tests/fixtures/confluence_mock/app.py`       | Minimal mock Confluence REST (FastAPI) for test data                                                 |
| `tests/fixtures/confluence_mock/Dockerfile`   | Image for mock service                                                                               |
| `tests/fixtures/confluence/pages.json`        | Seed pages (fa/en, tree structure)                                                                   |
| `frontend/src/components/ConfluencePanel.tsx` | UI: connect, select pages, index, status                                                             |

## Modified files

| Path                                        | Change                                                                                                        |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `app/pipeline/ingestion.py`                 | Add `run_documents(documents, original_filename, source_path)`; `run` delegates to it                         |
| `app/api/schemas.py`                        | Confluence request/response schemas (Test/Spaces/Pages/Index/Sync/Status)                                     |
| `app/api/routes.py`                         | Six endpoints: POST /test, /spaces, /pages, /index, /sync ; GET /status                                       |
| `app/config.py`                             | `confluence_timeout_seconds`, `page_limit`, `max_pages`, `embed_batch_size`, `allowed_hosts`                  |
| `docker-compose.yml`                        | frontend service, `./data` volume, confluence env, `--profile test` mock service                              |
| `Dockerfile`                                | unchanged (beautifulsoup4 added to requirements)                                                              |
| `requirements.txt`                          | add `beautifulsoup4`                                                                                          |
| `.env.example`                              | document new Confluence env vars                                                                              |
| `frontend/src/lib/api.ts`                   | typed `testConfluence`, `getConfluenceSpaces`, `getConfluencePages`, `indexConfluence`, `getConfluenceStatus` |
| `frontend/src/components/ChatContainer.tsx` | ConfluencePanel toggle button + state                                                                         |
| `frontend/src/components/MessageBubble.tsx` | render `metadata.url` as source link when present                                                             |

## Metadata per Confluence page (all scalar strings for Chroma)

page_id, space_key, page_title, page_version, last_modified, url, parent_page_id, source, original_filename=`confluence:<id>`, file_type=`confluence`.

---

## Acceptance checklist

- [ ] Phase 1: `ConfluenceClient` — test_connection works against mock with bearer AND basic; pagination + retry work
- [ ] Phase 2: `run_documents` added; `ConfluenceIngestionService.index` indexes pages idempotently; `/chat` returns cited answer from indexed page
- [ ] Phase 3: Six API endpoints functional; errors isolated per page (one bad page doesn't abort whole index)
- [ ] Phase 4: `ConfluencePanel` in UI; connect → select → index → show result/errors
- [ ] Phase 5: `docker compose --profile test up --build` — all services healthy; frontend reachable on 3000
- [ ] Phase 6: End-to-end smoke — index mock pages via UI → ask question → answer cites Confluence source
- [ ] Phase 7 (optional): incremental sync by `page_version`

---

## Work log

### 2026-11-07 (started)

- PLAN.md written (this file).
- `app/pipeline/ingestion.py`: added `run_documents()`; `run()` now delegates to it (no temp file needed for Confluence).
- Next: create `app/infrastructure/confluence_client.py` at correct path.
