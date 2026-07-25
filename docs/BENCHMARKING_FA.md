# راهنمای اجرای مقایسهٔ بازتولیدپذیر

در نسخهٔ ۰٫۲، خط‌پایه از سامانهٔ ارزیابی جدا شده است. در نتیجه روش پیشنهادی
بعداً می‌تواند بدون تغییر دادن داده‌ها، حمله‌ها، معیارها یا تحلیل آماری به
همان رابط افزوده شود. در حال حاضر فقط روش `paper_baseline` ثبت شده و هیچ
الگوریتمی به نام نوآوری ما حدس زده نشده است.

## ۱. ساخت manifest زوج‌ها

فایل CSV باید دست‌کم ستون‌های `pair_id`، `cover` و `secret` را داشته باشد.
ستون‌های اختیاری `split` و `seed` به‌ترتیب بخش قفل‌شدهٔ داده و بذر اجرا را
مشخص می‌کنند. مسیر نسبی از پوشهٔ خود manifest محاسبه می‌شود. نمونه در
[`pairs.example.csv`](../examples/pairs.example.csv) قرار دارد.

هر ترکیب `pair_id + seed` یک واحد اجرا است. واحد استنباط آماری همچنان خود
زوج‌تصویر (`pair_id`) باقی می‌ماند: seedهای تکراری ابتدا درون هر زوج میانگین
گرفته می‌شوند تا pseudoreplication رخ ندهد. ورودی تکراری، فایل مفقود و
شناسهٔ ناامن رد می‌شود. زوج‌های فایل نمونه صرفاً مثال اجرایی‌اند و به مقاله
نسبت داده نشده‌اند.

## ۲. اجرای خط‌پایه

```bash
python scripts/download_usc_sipi.py --output-dir data/usc_sipi

ctsteg benchmark \
  --manifest examples/pairs.example.csv \
  --config configs/paper_transmission.toml \
  --method paper_baseline \
  --output-dir results/baseline-v1 \
  --save-artifacts
```

پوشهٔ خروجی باید خالی یا هنوز ساخته‌نشده باشد تا نتایج اجرای قدیمی با اجرای
جدید مخلوط نشود. خروجی‌های اصلی:

- `results_long.csv`: تمام مقادیر خام برای هر زوج، seed، معیار و حمله؛
- `summary.csv`: آمار توصیفی و تعداد مقادیر نامتناهی؛
- `benchmark.json`: هش ورودی و خروجی، زمان‌ها و شکست‌ها؛
- `provenance.json`: هش داده، پیکربندی و کد ارزیابی، commit و وضعیت Git، محیط؛
- `artifacts/`: تصاویر اختیاری stego و بازیابی‌شده.

## ۳. افزودن نوآوری

روش جدید باید `MethodEmbedding` و `MethodExtraction` تعریف‌شده در
`ctsteg.methods` را برگرداند و با نامی مستقل مانند `proposed` ثبت شود. کد
خط‌پایه نباید برای سازگار کردن نوآوری ویرایش شود. کلید یا state لازم برای
بازیابی در `extraction_context` قرار می‌گیرد و در فایل خروجی ذخیره نمی‌شود.
سامانه کنترل می‌کند که روش، آرایه‌های مرجع cover و secret را عوض نکرده باشد
و تمام معیارها را با نسخهٔ محافظت‌شدهٔ ورودی محاسبه می‌کند.

پس از تعریف دقیق سازوکار نوآورانه، همان manifest و همان پیکربندی مشترک اجرا
می‌شود:

```bash
ctsteg benchmark \
  --manifest examples/pairs.example.csv \
  --config configs/paper_transmission.toml \
  --method proposed \
  --output-dir results/proposed-v1 \
  --save-artifacts
```

## ۴. مقایسهٔ آماری

```bash
ctsteg compare \
  --baseline results/baseline-v1/results_long.csv \
  --proposed results/proposed-v1/results_long.csv \
  --output-dir results/comparison-v1 \
  --bootstrap-resamples 10000 \
  --permutation-resamples 10000 \
  --seed 2026
```

پیش از تحلیل، یکسان بودن manifest، پیکربندی، گزینهٔ حمله، هش واقعی ورودی‌ها
و هش کد مشترک حمله/معیار کنترل می‌شود. سپس برای هر معیار:

- اختلاف‌ها با جهت معیار هم‌راستا می‌شوند؛ مقدار مثبت یعنی روش پیشنهادی بهتر
  بوده است؛
- seedهای تکراری درون هر زوج میانگین می‌شوند و bootstrap/آزمون روی زوج‌تصویر
  انجام می‌شود؛
- فاصلهٔ اطمینان ۹۵٪ bootstrap زوجی برای میانگین بهبود گزارش می‌شود؛
- آزمون sign-flip زوجی (دقیق تا ۱۶ زوج و Monte Carlo پس از آن) اجرا می‌شود؛
- آزمون Wilcoxon و اندازه‌اثر rank-biserial گزارش می‌شوند؛
- اصلاح چندگانهٔ Holm روی کل خانوادهٔ مقایسه اعمال می‌شود.

گزینه‌های `--allow-incomplete-pairs` و `--allow-provenance-mismatch` فقط برای
عیب‌یابی‌اند. خروجی حاصل از این استثناها بدون توضیح عدم‌تطابق، شاهد معتبر
مقایسهٔ کنترل‌شده نیست.

این تحلیل می‌تواند شواهد تجربی برتری را فراهم کند، اما به‌تنهایی نوآوری فنی
یا امنیت رمزنگاری را اثبات نمی‌کند. برای آن ادعاها باید تحلیل prior art،
مدل تهدید، ablation و نتایج منفی نیز طبق
[`NOVELTY_PROTOCOL.md`](NOVELTY_PROTOCOL.md) تکمیل شوند.
