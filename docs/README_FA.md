# راهنمای فارسی

این مخزن بازسازی مستقل و ممیزی‌پذیر مقاله
[Kumar et al. (2026)](https://doi.org/10.1038/s41598-026-41168-0)
است؛ کد اصلی نویسندگان نیست و به‌دلیل نبود پارامترهای تعیین‌کننده، ادعای
بازتولید عددی دقیق ندارد.

## مسیرهای پروژه

- P0: بازسازی منجمد مقاله با secret برابر 512×512؛
- DIGITAL_A_D: روش دیجیتال مستقل با secret برابر 128×128 و چهار روش C0 تا C3؛
- PDFB Gate: آزمون fail-closed برای اجرای واقعی MATLAB Contourlet Toolbox.

اجرای سریع تست‌های نرم‌افزار:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/check_p0_frozen.py
```

## برنامهٔ پژوهشی کم‌هزینه

اجرای نهایی از seedهای تکراری و ماتریس بزرگ استفاده نمی‌کند:

- ۴ زوج تصویر مرجع؛
- ۴ روش C0 تا C3؛
- Clean، JPEG 70، Gaussian 10 و S&P 0.03؛
- ۶۴ ردیف قطعی از فقط ۱۶ جاسازی؛
- حداکثر ۲۴ ردیف شرطی سخت فقط برای C0/C3؛
- سقف کل ۸۸ ردیف؛
- بدون power analysis و افزایش خودکار dataset.

مقدار داخلی لازم برای scrambling یا تولید noise فقط قابلیت بازتولید را
تأمین می‌کند و محور تکرار آزمایش نیست.

## اسناد اصلی

- [`RESEARCH_MASTER_PLAN_FA.md`](RESEARCH_MASTER_PLAN_FA.md): برنامهٔ جامع
  فارسی و ماتریس ۶۴/۸۸؛
- [`RESEARCH_PROTOCOL.md`](RESEARCH_PROTOCOL.md): قرارداد علمی؛
- [`EXPERIMENT_RUNBOOK.md`](EXPERIMENT_RUNBOOK.md): ترتیب اجرای سرور؛
- [`DATASET_AND_SPLIT_POLICY.md`](DATASET_AND_SPLIT_POLICY.md): چهار pair و
  قواعد داده؛
- [`PDFB_TRANSFORM_GATE_FA.md`](PDFB_TRANSFORM_GATE_FA.md): Gate واقعی PDFB؛
- [`CLAIMS_AND_EVIDENCE.md`](CLAIMS_AND_EVIDENCE.md): مرز ادعاها؛
- [`ROADMAP_FA.md`](ROADMAP_FA.md): وضعیت کوتاه پروژه؛
- [`README.md`](README.md): نقشهٔ کامل اسناد.

## مرز نتیجه

نتیجه فقط به چهار تصویر و شرایط اجراشده محدود است. نتیجهٔ خنثی یا منفی معتبر
است و مجوز اضافه‌کردن seed، حمله یا تصویر برای مثبت‌کردن نتیجه نیست.

AP/GP/HP و scrambling نیز بدون طراحی کلید، مدل تهدید و تحلیل مستقل، امنیت
رمزنگاری را اثبات نمی‌کنند.

