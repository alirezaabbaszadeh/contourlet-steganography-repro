# راهنمای فارسی

این مخزن بازسازی مستقل و ممیزی‌پذیر مقاله
[Kumar et al. (2026)](https://doi.org/10.1038/s41598-026-41168-0)
است؛ کد اصلی نویسندگان نیست و به علت نبود پارامترهای تعیین‌کننده، ادعای
بازتولید عددی دقیق ندارد.

سه پیکربندی جداگانه در `configs/` قرار داده شده است:

- `paper_literal.toml`: اجرای لفظیِ جاسازی فقط در زیرنوارهای پربسامد؛ این حالت
  امکان بازیابی کامل تصویر محرمانه را ندارد.
- `paper_recoverable_float.toml`: کنترل ریاضیِ قابل‌بازگشت بدون کوانتیزه‌کردن
  تصویر stego.
- `paper_transmission.toml`: حالت انتقال ۸ بیتی که اثر واقعی کوانتیزه‌سازی را
  آشکار می‌کند.

اجرای سریع:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
ctsteg demo --output-dir results/demo --size 128
```

برای اجرای چند زوج و ثبت کامل منشأ داده و محیط:

```bash
python scripts/download_usc_sipi.py --output-dir data/usc_sipi
ctsteg benchmark \
  --manifest examples/pairs.example.csv \
  --config configs/paper_transmission.toml \
  --method paper_baseline \
  --output-dir results/baseline-v1 \
  --save-artifacts
```

راهنمای کامل manifest، افزودن روش پیشنهادی و تحلیل bootstrap/Wilcoxon/Holm در
[`BENCHMARKING_FA.md`](BENCHMARKING_FA.md) آمده است.
وضعیت اولیه و زیرساخت مقایسه در [`ROADMAP_FA.md`](ROADMAP_FA.md) و
پیاده‌سازی جدید C0 تا C3 در [`DIGITAL_AD_FA.md`](DIGITAL_AD_FA.md) ثبت شده
است. جزئیات Gateهای اجرا نیز در
[`STAGE_GATE_STATUS.md`](STAGE_GATE_STATUS.md) قرار دارد.
دروازهٔ fail-closed مربوط به اجرای واقعی Contourlet Toolbox در
[`PDFB_TRANSFORM_GATE_FA.md`](PDFB_TRANSFORM_GATE_FA.md) مستند شده است.
برنامهٔ جامع توسعه، داده، آزمایش، شرط ادعای برتری و نگارش مقاله در
[`RESEARCH_MASTER_PLAN_FA.md`](RESEARCH_MASTER_PLAN_FA.md) قرار دارد و فهرست
کامل اسناد از [`README.md`](README.md) قابل دسترسی است.

برای افزودن روش پیشنهادی خودمان، خط‌پایه باید بدون تغییر باقی بماند و هر دو
روش با داده، ظرفیت، ضریب جاسازی، seed، حمله‌ها و تعریف معیارهای یکسان سنجیده
شوند. دستورکار آماری و نگارشی کامل در
[`NOVELTY_PROTOCOL.md`](NOVELTY_PROTOCOL.md) آمده است.
پروتکل از پیش‌تعریف‌شدهٔ نتیجهٔ اصلی در
[`RESEARCH_PROTOCOL.md`](RESEARCH_PROTOCOL.md)، دستور اجرای مرحله‌به‌مرحله در
[`EXPERIMENT_RUNBOOK.md`](EXPERIMENT_RUNBOOK.md) و سیاست محدودکردن ادعاها در
[`CLAIMS_AND_EVIDENCE.md`](CLAIMS_AND_EVIDENCE.md) ثبت شده‌اند.

توجه امنیتی: تبدیل AP/GP/HP فاقد کلید و قطعی است و از دید رمزنگاری مدرن
«رمزنگاری امن» محسوب نمی‌شود.
