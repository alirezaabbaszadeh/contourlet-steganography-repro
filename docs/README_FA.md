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

برای افزودن روش پیشنهادی خودمان، خط‌پایه باید بدون تغییر باقی بماند و هر دو
روش با داده، ظرفیت، ضریب جاسازی، seed، حمله‌ها و تعریف معیارهای یکسان سنجیده
شوند. دستورکار آماری و نگارشی کامل در
[`NOVELTY_PROTOCOL.md`](NOVELTY_PROTOCOL.md) آمده است.

توجه امنیتی: تبدیل AP/GP/HP فاقد کلید و قطعی است و از دید رمزنگاری مدرن
«رمزنگاری امن» محسوب نمی‌شود.
