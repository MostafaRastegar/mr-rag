# استفاده از یکپارچه‌سازی کانفلوئنس (Confluence Integration)

این DOCUMENT نحوه پیکربندی، صدا زدن API و استفاده از پنل کاربری برای اندیس‌سازی صفحات کانفلوئنس و انجام RAG روی آن‌ها را توضیح می‌دهد.

## ۱. متغیرهای محیطی

در `.env` (یا `.env.example`):

```env
# اتصال به دیتابیس وکتور (قبلا وجود داشت)
CHROMA_HOST=chromadb

# کانفلوئنس
CONFLUENCE_TIMEOUT_SECONDS=60
CONFLUENCE_PAGE_LIMIT=100
CONFLUENCE_MAX_PAGES=2000
CONFLUENCE_EMBED_BATCH_SIZE=64

# محدودیت هاست برای جلوگیری از SSRF (خالی = همه مجاز، با هشدار لاگ)
CONFLUENCE_ALLOWED_HOSTS=
```

## ۲. احراز هویت

دو حالت پشتیبانی می‌شود (انتخاب می‌شود از طریق `auth_type`):

| حالت | توضیح | Hearders |
|------|-------|----------|
| `bearer` | کانفلوئنس سرور/دیتاسنتر (PAT) | `Authorization: Bearer <token>` |
| `basic` | کانفلوئنس کلود (ایمیل + توکن API) | `Authorization: Basic base64(email:token)` |

توکن فقط در حافظه نشست (session) نگه‌داری می‌شود، در localStorage یاBackend persisted نمی‌شود. تمام endpointها POST هستند تا توکن در URL / لاگ‌ها ظاهر نشود.

## ۳. endpointهای API (بنیادی: `http://localhost:8080`)

### POST `/confluence/test` — تست اتصال و اعتبارسنجی
درخواست:
```json
{
  "base_url": "https://confluence.sazeman.ir",
  "auth_type": "bearer",
  "token": "PERSONAL_ACCESS_TOKEN"
}
```
پاسخ: `{ "ok": true, "user": "Test User", "spaces_count": 2 }`

برای کلود:
```json
{
  "base_url": "https://sazeman.atlassian.net/wiki",
  "auth_type": "basic",
  "email": "user@sazeman.ir",
  "token": "API_TOKEN"
}
```

### POST `/confluence/spaces` — لیست فضاهای قابل دسترسی
درخواست مشابه `/test` با فیلد اختیاری `limit`.
پاسخ: `{ "spaces": [{"key": "TEST", "name": "TEST"}], ... }`

### POST `/confluence/pages` — لیست صفحات
.query parmaeters بدنه:
```json
{
  "base_url": "...",
  "auth_type": "bearer",
  "token": "...",
  "space_key": "TEST",
  "parent_page_id": null,
  "start": 0,
  "limit": 100
}
```
یا برای زیرصفحات: `parent_page_id="1001"` و بدون `space_key`.
پاسخ: `{ "pages": [{id, title, space_key, url, version}], "has_more": true/false }`

### POST `/confluence/index` — اندیس‌سازی صفحات (سه حالت)
```json
{
  "base_url": "...",
  "auth_type": "bearer",
  "token": "...",
  "mode": "ids",           // "ids" | "space" | "subtree"
  "page_ids": ["1001", "1002"],   // فقط وقتی mode="ids"
  "space_key": "TEST",     // فقط وقتی mode="space"
  "root_page_id": "1001",  // فقط وقتی mode="subtree"
  "recursive": true        // فقط وقتی mode="subtree" (صفحات زیرمجموعه)
}
```
پاسخ:
```json
{
  "status": "success",
  "pages_indexed": 4,
  "pages_failed": 0,
  "chunks_ingested": 4,
  "errors": []
}
```
یک صفحه ناموفق کل اندیس را متوقف نمی‌کند؛ خطاها در `errors` بازگردانده می‌شوند.
اندیس‌سازی idempotent است: قبل از افزودن، تکه‌های قبلی همان `page_id` حذف می‌شوند.

### POST `/confluence/sync` — هم‌زمانی مجدد (بدنه مشابه `/index`)
### GET `/confluence/status` — وضعیت آخرین هم‌زمانی (بدون بدنه)

## ۴. RAG روی محتوای اندیس شده

پس از اندیس‌سازی، سوال را از طریق endpoint چت bestaward بپرسید:

```http
POST /chat
Content-Type: application/json

{
  "message": "شرکت ما چطور تاسیس شد؟"
}
```

پاسخ حاوی `sources` است؛ هر منبع دارای `metadata.page_title` و `metadata.url` است که در یک UI به صورت لینک قابل کlick نمایش داده می‌شود (`pages/viewpage.action?pageId=<id>`).

## ۵. استفاده از پنل کاربری (Frontend)

1. دکمه **کانفلوئنس** در هدر چت را بزنید (نمایش پنل).
2. آدرس کانفلوئنس و توکن (یا ایمیل + توکن برای کلود) را وارد کنید و **تست اتصال** بزنید.
3. روش انتخاب Pages را انتخاب کنید:
   - **آی‌دی صفحات**: لیستی از IDها با کاما (مثلاً `1001, 1002`)
   - **کل فضا**: کلید فضا را انتخاب و صفحات را بارگذاری کنید
   - **زیردرخت**: صفحه ریشه و فعال‌سازی «كل صفحات زیرمجموعه» برای recursion
4. صفحات مورد نظر را تیک بزنید (در حالت space/subtree) و **اندیس‌سازی избран Pages** بزنید.
5. نتیجه (تعداد اندیس شده، شکست، قطعه ذخیره شده) نمایش داده می‌شود.
6. حالا در چت سوال بپرسید؛ منابع کانفلوئنس به عنوان لینک نمایش داده می‌شوند.

## ۶. Docker (-stack کامل)

سرویس‌ها:
- `app` (FastAPI، پورت 8080)
- `chromadb` (پورت 8000)
- `frontend` (Next.js، پورت 3000)
- `confluence-mock` (فقط با `--profile test`، پورت 8091)

### اجرا با داده‌های تست

```bash
docker compose --profile test up --build
```

سرویس `confluence-mock` یک API limitied Confluence است که با توکن `test-token` پاسخ می‌دهد و ۵ صفحه Seed ( fa/en، ساختار درختی ) دارد. پس از بالا آمدن، از پنل کاربری با:
- `base_url`: `http://localhost:8091`
- `auth_type`: `bearer`
- `token`: `test-token`

اتصال را تست کنید و صفحات فضا `TEST` را اندیس کنید، سپس RAG را امتحان کنید.

### متغیر Docker Compose

```env
CONFLUENCE_ALLOWED_HOSTS=confluence.sazeman.ir
```

سرویس `app` پوشه `./data` را مونت می‌کند تا لاگ هم‌زمانی (`confluence_sync_log.json`) و دیتابیس‌های لاگِ درایو پstüt کنند.

## ۷. نکات امنیتی

- توکن در بدنه درخواست می‌رود (POST)، نه در URL.
- `CONFLUENCE_ALLOWED_HOSTS` لیست هاست‌های مجاز است؛ خالی بودن همه را مجاز می‌دارد (با لاگ هشدار) — در تولید propensity، هاست‌های مجاز را محدود کنید.
- هیچ توکنی در localStorage / دیتابیس Backend ذخیره نمی‌شود.
- خطاهای هر صفحه به صورت مجزا ثبت شده و کل عملیات را متوقف نمی‌کنند.
