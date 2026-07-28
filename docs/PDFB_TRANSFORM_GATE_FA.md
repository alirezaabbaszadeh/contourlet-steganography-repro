# دروازهٔ مرحلهٔ صفر تبدیل PDFB

این مرحله فقط یک تفسیر صریح از Contourlet Toolbox متلب را ممیزی می‌کند. حتی
در صورت موفقیت، نتیجه به‌عنوان تنظیمات نامشخص نویسندگان مقاله معرفی نمی‌شود.

پیکربندی
[`pdfb_matlab_gate_v1.toml`](../configs/digital_ad/pdfb_matlab_gate_v1.toml)
فرض‌های زیر را قفل می‌کند:

- فیلتر هرمی `9-7`؛
- فیلتر جهت‌دار `pkva`؛
- بردار جهت‌ها `[2,2,2,2]`؛
- چهارمین سطح از coarse به‌عنوان candidate pool؛
- ورودی قطعی 512×512؛
- حداقل ظرفیت 222,360 ضریب؛
- سه probe داخلی برای هر زیرباند واجد شرایط.

عدد 262,144 از پیش پذیرفته نمی‌شود. اسکریپت
[`audit_pdfb_stage0.m`](../matlab/audit_pdfb_stage0.m) شکل و تعداد واقعی همهٔ
زیرباندها را از خروجی `pdfbdec` استخراج می‌کند.

برای هر probe، یک ضریب یک واحد تغییر می‌کند، تصویر با `pdfbrec` ساخته و
دوباره با `pdfbdec` تحلیل می‌شود. سپس gain ضریب هدف، بیشترین cross-talk و
انرژی خارج از هدف ثبت می‌شود.

## شروط عبور

| کنترل | شرط |
|---|---:|
| تعداد جهت‌های سطح منتخب | دقیقاً 4 |
| ظرفیت | حداقل 222,360 |
| بیشینهٔ خطای بازسازی | حداکثر `1e-8` |
| تعداد probe | حداقل 3 برای هر زیرباند |
| کمینهٔ self-gain | حداقل `0.99` |
| بیشینهٔ cross-talk | حداکثر `0.01` |
| نسبت انرژی L2 خارج از هدف | حداکثر `0.05` |

شکست هر شرط به‌عنوان نتیجهٔ منفی معتبر با `gate_passed=false` ذخیره می‌شود.
evidence ناقص، تغییر پارامترها، ورودی متفاوت یا نبودن Hash فایل‌های toolbox
کاملاً رد می‌شود.

## اجرا

ابتدا بدون نیاز به MATLAB، برنامهٔ دقیق اجرا ساخته می‌شود:

```bash
ctsteg pdfb-plan \
  --spec configs/digital_ad/pdfb_matlab_gate_v1.toml \
  --toolbox-path /absolute/path/to/contourlet_toolbox \
  --raw-evidence results/pdfb-stage0/pdfb-audit-raw.json \
  --output results/pdfb-stage0-plan.json
```

اجرای واقعی:

```bash
ctsteg pdfb-audit \
  --spec configs/digital_ad/pdfb_matlab_gate_v1.toml \
  --toolbox-path /absolute/path/to/contourlet_toolbox \
  --matlab-scripts matlab \
  --timeout-seconds 1800 \
  --output-dir results/pdfb-stage0
```

موفقیت Stage 0 فقط اجازهٔ بازبینی انسانی می‌دهد. backend هنوز برای embedding
فعال نمی‌شود، Benchmark انبوه مجاز نیست و ادعای برابری با تبدیل نویسندگان یا
برتری مستقیم نسبت به مقاله همچنان ممنوع است.
