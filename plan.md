## تحلیل APIs موجود

پس از بررسی فایل‌های backend و frontend، دیدم که frontend تنها بخشی از قابلیت‌های APIها را پیاده‌سازی کرده است. در ادامه وضعیت فعلی را نشان می‌دهم:

### APIs پیاده‌سازی شده در frontend:
- ✅ `/health` - بررسی سلامت سرور
- ✅ `/chat` - ارسال پیام (با پاسخ کامل)
- ✅ `/chat/stream` - ارسال پیام (با پاسخ استریم)
- ✅ `/search` - جستجوی مستقیم در اسناد
- ✅ `/upload` - بارگذاری فایل
- ✅ `/documents` - لیست تمام اسناد
- ✅ `/documents/{doc_id}` - دریافت جزئیات یک سند
- ✅ `/documents/{doc_id}` - حذف سند
- ✅ `/admin/stats` - آمار کلی سیستم
- ✅ `/admin/scheduler/status` - وضعیت اسکجولر
- ✅ `/admin/scheduler/run` - اجرای دستی اسکجولر
- ✅ `/admin/cache/clear` - پاکسازی کش
- ✅ `/metrics` - متریک‌های Prometheus
- ✅ `/conversations` - لیست گفتگوها
- ✅ `/conversations/{conv_id}` - دریافت گفتگو
- ✅ `/conversations` - ایجاد گفتگو
- ✅ `/conversations/{conv_id}` - به‌روزرسانی گفتگو
- ✅ `/conversations/{conv_id}` - حذف گفتگو

## برنامه پیاده‌سازی ✅ (انجام شده)

### گام 1: اضافه کردن توابع API جدید در `frontend/src/lib/api.ts` ✅
تمامی توابع API مورد نیاز اضافه شده‌اند:
- Document management: `getDocuments`, `getDocument`, `deleteDocument`
- Admin: `getAdminStats`, `getSchedulerStatus`, `runScheduler`, `clearCache`
- Metrics: `getMetrics`
- Conversations: `getConversations`, `getConversation`, `createConversation`, `updateConversation`, `deleteConversationApi`

### گام 2: ساخت کامپوننت‌های جدید ✅
- `DocumentsPanel.tsx` - پنل مدیریت اسناد (نمایش لیست، جزئیات، حذف، خطا، خالی)
- `AdminPanel.tsx` - پنل ادمین (آمار سیستم، وضعیت اسکجولر + اجرای دستی، پاکسازی کش)

### گام 3: ادغام با UI موجود ✅
- دکمه‌های `اسناد` (با آیکون FileText) و `مدیریت` (با آیکون Activity) به Header اضافه شده
- مودال‌های DocumentsPanel و AdminPanel با کلیک روی دکمه‌ها نمایش داده می‌شوند

### نکات باقی‌مانده:
- توابع Conversations API در `api.ts` وجود دارند ولی UI هنوز از IndexedDB محلی برای گفتگوها استفاده می‌کند (قابل ارتقا)
