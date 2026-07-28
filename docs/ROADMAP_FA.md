# نقشه‌راه فعلی و دروازه‌های بعدی

شرح جامع در
[`RESEARCH_MASTER_PLAN_FA.md`](RESEARCH_MASTER_PLAN_FA.md) قرار دارد. این فایل
فقط وضعیت اجرایی کوتاه را نگه می‌دارد.

## تکمیل‌شده

### P0

- بازسازی مستقل AP/GP/HP و مسیر نیمه‌کور؛
- ممیزی تناقض‌ها و پارامترهای مفقود مقاله؛
- پیکربندی‌های لفظی، float-control و انتقال ۸ بیتی؛
- Freeze شش فایل عددی و کنترل CI؛
- benchmark و آمار زوجی با provenance.

### DIGITAL_A_D

- Secret برابر 128×128 و تقسیم 4+4 بیت Base/Detail؛
- payload خام 131,072 و transport ثابت 222,360 بیت؛
- RS، CRC، scrambling، interleaving و header ثابت؛
- C0، C1، C2 و C3؛
- A مبتنی بر انرژی، واریانس، آنتروپی و stability؛
- D مبتنی بر حفاظت نابرابر Base/Detail؛
- کنترل PSNR برابر 45 dB؛
- حمله‌های دیجیتال JPEG، Gaussian و Salt-and-Pepper؛
- calibration guard، benchmark، factorial analysis و failure-aware metrics؛
- کنترل Haar و ثبت شکست proxy بدون تغییر هدف.

### PDFB Gate

- پیکربندی صریح `9-7`، `pkva` و `[2,2,2,2]`؛
- اسکریپت ممیزی MATLAB؛
- اعتبارسنج fail-closed پایتون؛
- اندازه‌گیری ساختار، ظرفیت، reconstruction و coefficient probes؛
- CLI، تست، CI و مستندات.

## در حال انتظار

1. اجرای واقعی MATLAB و Contourlet Toolbox؛
2. بازبینی انسانی evidence؛
3. ساخت adapter نسخه‌دار PDFB؛
4. Clean C0 روی PDFB در payload و PSNR قفل‌شده؛
5. پیاده‌سازی preflight داده و aggregate primary analysis؛
6. انتخاب dataset دارای مجوز، power analysis و قفل manifest؛
7. calibration و pilot نهایی؛
8. protocol lock؛
9. benchmark قفل‌شده و تولید خودکار نتایج مقاله.

## شرط ادامه

اگر PDFB کمتر از 222,360 ضریب واجد شرایط داشته باشد، reconstruction یا probes
شکست بخورند، هیچ proxy جدیدی ساخته نمی‌شود و payload کاهش نمی‌یابد. نتیجهٔ
منفی ذخیره و مرز مقاله به مطالعهٔ کنترل‌شدهٔ دیجیتال محدود می‌شود.

## شرط ادعای برتری

برتری C3 بر C0 فقط طبق معیار اصلی و شرط موفقیت
[`RESEARCH_PROTOCOL.md`](RESEARCH_PROTOCOL.md) نوشته می‌شود. برتری مستقیم
نسبت به مقاله تا harmonization کامل Transform، payload، داده، حمله و معیار
ممنوع است.
