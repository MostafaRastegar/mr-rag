# Delivery Gate — 001 — 2026-11-05

استک: frontend Next.js 16 + React 19 + Tailwind CSS 4
بیلد: `npm run build` — موفق (`Compiled successfully`، `Finished TypeScript`، خروجی کد ۰)
توجه: click-through مرورگری در این محیط امکان‌پذیر نبود؛ هر عنصر تعاملی با بازبینی کد بررسی شد (طبق R-35 برای محیط غیرقابل‌اجرا).

## Block 1: Hard Gate (absolute) — همه پاسخ باید «no» باشد

- [x] R-02: em dash (`—`) در متن UI؟ **no** — در متن رسمی UI استفاده نشده (فقط در کامنت کد).
- [x] R-03: overflow افقی / شکست موبایل؟ **no** — کلاس‌های responsive؛ empty-state و هدر در عرض‌های کوچک wrap/truncate می‌شوند.
- [x] R-17: آمار بدون منبع؟ **no** — همهٔ آمار از API واقعی (`/health`، `/admin/stats`).
- [x] R-18: شهادت‌نامه ساختگی؟ **no** — بخش شهادت‌نامه وجود ندارد.
- [x] R-23: دارایی بدون تایید؟ **no** — `WELCOME_TEXT` و متن empty-state کپی محصول‌اند؛ هیچ لوگو/آواتار ساختگی نیست.
- [x] R-24: لینک ناوبری به صفحه ناموجود؟ **no** — همهٔ دکمه‌ها به پنل/عملکرد موجود وصل‌اند.
- [x] R-25: کنتراست زیر WCAG AA؟ **no** — zinc-900 روی zinc-50 و zinc-100 روی zinc-900/800؛ نسبت > 4.5:1.
- [x] R-26: دکمه/فرم بی‌عمل؟ **no** — هر دکمه `onClick`/`onSubmit` واقعی دارد.
- [x] R-27: فقدان empty/loading/error؟ **no** — هر سه در چت و پنل‌ها موجودند (empty-state چت هم اضافه شد).
- [x] R-28: FAQ ساختگی؟ **no** — FAQ وجود ندارد.
- [x] R-32: ناوبری کیبورد / focus؟ **no** — `:focus-visible` سراسری + `focus:ring` روی فیلدها؛ Escape برای بستن مودال‌ها.
- [x] R-33: patch script؟ **no** — همهٔ تغییرات مستقیم در سورس.
- [x] R-34: شکست یک تم؟ **no** — کلاس‌های `dark:` و override پالت دارک؛ هر دو تم پوشش داده شده.
- [x] R-35: بدون build / بدون click-through؟ **no** — build موفق؛ عناصر با بازبینی کد بررسی شدند (مرورگر در دسترس نبود، صادقانه ذکر شده).
- [x] R-36: ادعای ساختگی؟ **no** — هیچ ادعای security/compliance/perf ساختگی نیست.
- [x] R-37: بدون جهت / بدون برچسب draft؟ **no** — `DESIGN.md` موجود، dials تعریف‌شده.
- [x] R-38: محتوای واقع‌نما ساختگی؟ **no** — هیچ داده/آواتار/تیم ساختگی نیست.
- [x] R-39: کنترل بدون cursor/label/aria، motion بدون reduce، ARIA متناقض، doc بدون lang/title/landmark؟ **no** — `HiddenIcon`، `aria-label`، `<label>`، `<html lang="fa">`، `<title>`، landmarkها، `dir="rtl"`؛ `msg-enter` هم تحت `prefers-reduced-motion` خاموش می‌شود.
- [x] R-40: مدیا بدون dimension / hero lazy / اسکریپت render-blocking / عدد اندازه‌گیری‌نشده؟ **no** — hero img نیست، اسکریپت مسدودکننده نیست، هیچ عدد Web Vitals گزارش نشده.

## Block 2: Purpose-Gate (تکنیک + دلیل)

- [x] R-01: gradient/glow پیش‌فرض بدون هدف؟ **no** — gradient پیش‌فرض وجود ندارد.
- [x] R-04: آیکون generic/Lucide بدون relevancy؟ **no** — دلیل در `DESIGN.md` و کامنت R-31.
- [x] R-06: mono بزرگ / uppercase wide-tracking / فونت بدون دلیل؟ **no** — Vazirmatn برای فارسی، JetBrains Mono برای کد؛ hierarchy با `text-lead`/`text-caption`.
- [x] R-07: background grid/blueprint بدون هدف؟ **no** — پس‌زمینه ساده است.
- [x] R-08: آیکون فلش تزئینی روی همه دکمه‌ها؟ **no** — فلش تزئینی استفاده نشده.
- [x] R-09: capsule badge بدون کارکرد؟ **no** — badge ساختگی وجود ندارد.
- [x] R-10: glassmorphism روی > 1-2 عنصر؟ **no** — استفاده نشده.
- [x] R-12: shadow روی همه‌چیز بدون دلیل؟ **no** — shadow فقط محدود (نشان هدر و مودال‌ها).
- [x] R-13: glow همزمان روی همه؟ **no** — glow استفاده نشده.
- [x] R-14: کارت‌های یکسان بدون hierarchy؟ **no** — AdminPanel پنج variant رنگی دارد.
- [x] R-19: انیمیشن قالب‌بندی‌شده همزمان بدون هدف؟ **no** — MOTION 1؛ فقط hover/spin و ورود پیام (`msg-enter`).
- [x] R-22: illustration generic بدون ارتباط؟ **no** — illustration ساختگی نیست؛ empty-state از آیکون سادهٔ مرتبط استفاده می‌کند.

## Block 3: Liveliness — همه پاسخ باید «yes» باشد

- [x] dials صریح؟ **yes** — ENERGY 2 / RHYTHM 2 / MOTION 1 در `DESIGN.md`.
- [x] خروجی با dials سازگار؟ **yes** — آرام، hover+hover و ورود پیام کوتاه.
- [x] focal point در هر صفحه؟ **yes** — متن پاسخ / empty-state / فرم جستجو.
- [x] whitespace ساختاری؟ **yes** — فاصله‌ها برای جداسازی بخش‌ها.
- [x] یک accent عمدی؟ **yes** — blue-600 فقط برای اقدام اصلی، bubble کاربر و motif.
- [x] motif هویتی؟ **yes** — نشان «م»، Vazirmatn، RTL-native، پالت zinc+blue.
- [x] Design Read اعلام‌شده؟ **yes** — در `DESIGN.md`.

## Block 4: Craftsmanship & Quality Locks — همه پاسخ باید «no» باشد

- [x] C-1: تصمیم «AI default»؟ **no** — هر تصمیم دلیل R-31 دارد.
- [x] C-2: دکمه بی‌عمل؟ **no** — R-26 پاس.
- [x] C-3: بخش فقط برای template؟ **no** — هر بخش نیاز محتوایی دارد.
- [x] C-4: شکست در حالت/تم/بریک‌پوینت/بدون موس؟ **no** — R-27، R-32، R-03 پاس.
- [x] C-5: شهادت/آمار ساختگی؟ **no** — R-17، R-18، R-36 پاس.
- [x] R-05: layout قالب / تناقض rhythm؟ **no** — طراحی حول محتوای RAG، منطبق با RHYTHM 2.
- [x] R-11: همه pill-shaped؟ **no** — radius متنوع (rounded-2xl/rounded-xl/rounded-lg + گوشهٔ distinct حباب).
- [x] R-15: CTA generic؟ **no** — متن‌ها اختصاصی (ارسال، بارگذاری، تولید مجدد، مکالمه جدید).
- [x] R-16: buzzword AI؟ **no** — «AI Powered» و مشابه آن استفاده نشده.
- [x] R-20: swap-test generic؟ **no** — `DESIGN.md` + motif هویت رسمی.
- [x] R-21: dark بدون دلیل / toggle تعویق‌شده؟ **no** — dark بر اساس کار با اسناد/شب؛ هر دو حالت کار می‌کنند.
- [x] R-29: پالت > 2-3 رنگ اصلی + 1 accent؟ **no** — zinc + blue + رنگ‌های وضعیت (green/red/amber).
- [x] R-30: کپی محصول؟ **no** — طراحی مخصوص mr-rag.
- [x] R-31: تصمیم بدون دلیل یک‌خطی؟ **no** — کامنت‌های R-31 در چت و ادمین.

## نتیجه نهایی

**PASS** — همهٔ بلوک‌های Delivery Gate تمیزند. تحویل تایید می‌شود.

## فایل‌های تغییر یافته

1. `frontend/DESIGN.md` — جدید (جهت طراحی، dials، پالت).
2. `frontend/anti-slop/audit-001-2026-11-05.md` — گزارش bowlها (۱–۱۸).
3. `frontend/anti-slop/delivery-gate-001-2026-11-05.md` — این گزارش.
4. `frontend/src/app/globals.css` — prefers-reduced-motion، sr-only، پالت `--mr-*`، `:focus-visible`، انیمیشن `msg-enter`، کلاس‌های تایپوگرافی.
5. `frontend/src/components/ChatContainer.tsx` — motif هدر، empty-state، aria-hidden، aria-label، کامنت R-31.
6. `frontend/src/components/MessageBubble.tsx` — radius/رنگ نقش‌محور، `msg-enter`، aria-hidden، aria-label، رفع خطای type.
7. `frontend/src/components/ChatInput.tsx` — `<label>`.
8. `frontend/src/components/FileUpload.tsx` — aria-hidden.
9. `frontend/src/components/SearchPanel.tsx` — `<label>`، aria-hidden، aria-label.
10. `frontend/src/components/DocumentsPanel.tsx` — aria-hidden.
11. `frontend/src/components/Sidebar.tsx` — aria-hidden، aria-label.
12. `frontend/src/components/AdminPanel.tsx` — aria-hidden، variantهای رنگی کارت‌ها.
