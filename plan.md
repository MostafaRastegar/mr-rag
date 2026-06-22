# برنامه توسعه ویژگی‌های اولویت متوسط

با توجه به اینکه شما سرور FastAPI و ChromaDB را دستی اجرا کرده‌اید، من هر feature را در یک **branch مجزا** توسعه می‌دهم و در انتهای هر کدام از شما می‌خواهم سرور را restart کنید تا صحت عملکرد را تأیید کنیم.

---

## ترتیب پیاده‌سازی (با در نظر گرفتن وابستگی‌ها)

### 1️⃣ حذف/به‌روزرسانی در Vector Store
**Branch:** `feature/vector-store-crud`
- اضافه کردن متدهای `delete(ids)` و `update(ids, embeddings)` به `VectorStorePort`
- پیاده‌سازی در `ChromaVectorStore`
- **تأیید:** بعد از restart، با یک درخواست ساده curl تست می‌کنیم

### 2️⃣ مدیریت اسناد (Document CRUD)
**Branch:** `feature/document-management`
- `GET /documents` — لیست اسناد با metadata
- `GET /documents/{id}` — جزئیات سند + chunk‌های آن
- `DELETE /documents/{id}` — حذف سند و chunk‌های مرتبط
- **تأیید:** با curl یک فایل upload می‌کنیم، لیست می‌گیریم، حذف می‌کنیم

### 3️⃣ اندپوینت‌های Admin
**Branch:** `feature/admin-endpoints`
- `POST /admin/scheduler/run` — اجرای دستی scheduler
- `GET /admin/scheduler/status` — آخرین وضعیت fetch
- `POST /admin/cache/clear` — پاک کردن کش‌ها
- `GET /admin/stats` — آمار کلی (تعداد اسناد، chunk‌ها، وضعیت کش)
- **تأیید:** با curl اندپوینت‌ها را تست می‌کنیم

### 4️⃣ تاریخچه مکالمات در Backend
**Branch:** `feature/conversation-history`
- مدل `Conversation` و `Message` در domain
- `ConversationRepositoryPort` در ports
- پیاده‌سازی `SQLiteConversationRepository`
- اندپوینت‌های CRUD برای مکالمات
- **تأیید:** چند مکالمه ایجاد می‌کنیم، لیست می‌گیریم، حذف می‌کنیم

### 5️⃣ Metrics / Monitoring
**Branch:** `feature/metrics-monitoring`
- Prometheus metrics با `prometheus-client`
- Metrics: request count, latency, cache hit/miss, vector store count
- `GET /metrics` اندپوینت
- **تأیید:** با curl metrics را بررسی می‌کنیم

### 6️⃣ پشتیبانی PDF
**Branch:** `feature/pdf-support`
- اضافه کردن `PDFDocumentLoader` با `PyMuPDF`
- ثبت در `AutoDocumentLoader`
- **تأیید:** یک فایل PDF آپلود و ingest می‌کنیم

---

## قوانین کار

1. **هر feature در branch جداگانه** از `develop` ایجاد می‌شود
2. بعد از اتمام هر feature، از شما می‌خواهم **سرور را restart** کنید
3. با curl یا فرانت‌اند تست می‌کنیم
4. بعد از تأیید، به feature بعدی می‌رویم
5. در انتها همه را به `develop` merge می‌کنیم
