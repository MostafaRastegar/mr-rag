# DESIGN.md — mr-rag Frontend

## هویت محصول
mr-rag یک سیستم بازیابی-تولید افزایشی (RAG) با آگاهی فارسی برای مدیریت دانش و اسناد سازمانی است.

## مخاطب هدف
کارکنان سازمانی، محققین و کاربران فارسی‌زبان که به جستجو، پرسش و پاسخ از اسناد سازمانی نیاز دارند.

## زبان دیداری
RTL-native (راست به چپ)، تمیز، حرفه‌ای و قابل اعتماد. بدون سلوپ AI: gradients پیش‌فرض، آیکون sparkle/star بدون هدف، یا ادعای fabrication نیست. یک فوکال پوینت در هر صفحه (متن پاسخ یا فرم جستجو).

## پالت رنگی (بحداکثر ۲-۳ رنگ اصلی + ۱ رنگ dominance)
- رنگ پایه: zinc (ب 없게/خاکستری) — neutrality برای خواندن اسناد
- رنگ dominance: blue-600 — اقدامات اصلی (ارسال، بارگذاری، حذف)
- رنگ-state: green (موفق)، red (خطا/توقف)، amber (هشدار)

## تایپوگرافی
- بدنه فارسی: Vazirmatn (next/font/google) — خوانایی بالا در RTL فارسی
- کد/مونو: JetBrains Mono / Fira Code — برای بلاک کد و اسناد فنی
- fallback: Tahoma, system-ui

## حالت رنگی (Theme)
Light و Dark Toggle — هر دو حالت باید کاملاً کار کنند. dark به دلیل کار با اسناد و کاهش vuesی شب، نه به raison "tech-looking".

## دials (بלתل تغییر نباشد)
- ENERGY 2 (Balanced) — حرفه‌ای و دوستانه
- RHYTHM 2 (Balanced) — تکرار هماهنگ با شکست‌های کمی
- MOTION 1 (Hover states only) — ابزار productivity،IE虑 distraction کم

## mood
متمرکز، آرام، قابل اعتماد.
