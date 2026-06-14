---
name: mr-rag-11-scheduler
description: Automated cron ingestion with JWT auth, paginated fetching, and exponential backoff
---

# mr-rag-11-scheduler

## Usage

Use this skill when modifying the scheduler, adding new external API integrations, changing retry logic, or troubleshooting automated ingestion.

## Steps

1. Configure scheduler settings in `.env` (API URL, credentials, interval)
2. JWT authentication with auto-refresh (23h cache window)
3. Fetch paginated data from Scraper API
4. Save fetched data to a temp JSON file
5. Run IngestionPipeline on the temp file
6. Log last fetch timestamp, document count, and status
7. Clean up temp file in `finally` block
8. Retry on failure with exponential backoff

## Flow

```
Scheduler (every N minutes)
  → POST /api/v1/token/ (JWT)
  → GET /api/v1/messages/search/?page=1...N
  → save_to_temp_file()
  → IngestionPipeline.run()
  → log_last_fetch()
  → delete_temp_file()
  → On error: retry with exponential backoff
```

## JWT Authentication

```python
class SchedulerAuth:
    def get_token(self) -> str:
        if time.time() < self._token_expiry:
            return self._token  # cached
        response = requests.post(f"{self._base_url}/api/v1/token/", ...)
        self._token = response.json()["access"]
        self._token_expiry = time.time() + 82800  # 23h
        return self._token
```

## Exponential Backoff

```python
delay = RETRY_DELAY_SECONDS  # 60s
for attempt in range(MAX_RETRIES):  # 5 attempts
    try:
        return _execute_job()
    except Exception as e:
        logger.error("Attempt %d/%d failed: %s", attempt + 1, MAX_RETRIES, str(e))
        if attempt < MAX_RETRIES - 1:
            time.sleep(delay)
            delay *= 2  # 60 → 120 → 240 → 480 → 960
```

## Temp File Lifecycle

```python
temp_path = f"data/temp_{int(time.time())}.json"
try:
    with open(temp_path, "w") as f:
        json.dump(messages, f)
    ingestion_pipeline.run(temp_path)
finally:
    if os.path.exists(temp_path):
        os.remove(temp_path)
```

## Should / Should Not

✅ Do: Use `finally` block to ensure temp file cleanup
✅ Do: Cache JWT tokens and auto-refresh before expiry
✅ Do: Implement exponential backoff for retries
✅ Do: Log every fetch attempt and its result
❌ Don't: Leave temp files after failed ingestion
❌ Don't: Hardcode credentials — use environment variables
❌ Don't: Skip pagination — fetch ALL pages