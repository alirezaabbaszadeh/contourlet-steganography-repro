# راهنمای اجرای موازی، Cache و Resume

زیرساخت اجرای پژوهش اکنون این قابلیت‌ها را دارد:

- اجرای موازی کنترل‌شده تا سقف ۱۶ worker؛
- جلوگیری از موازی‌سازی تو‌در‌تو در BLAS/OpenMP؛
- ۱۶ checkpoint مستقل برای جاسازی و Clean؛
- checkpoint مستقل برای هر ارزیابی حمله؛
- cache محتوایی با SHA-256 و اعتبارسنجی کامل همهٔ فایل‌ها؛
- ذخیرهٔ atomic؛
- ادامهٔ خودکار پس از قطع برق، kill یا reboot؛
- نگهداری attemptهای ناموفق و quarantine خروجی خراب؛
- خروجی CSV، JSON، JSONL و در صورت نصب extra پژوهش، Parquet؛
- بستهٔ دانلودی مستقل همراه با `checksums.sha256`؛
- اعتبارسنجی تک‌تک فایل‌های archive پیش از انتشار و پیش از بازاستفاده؛
- جلوگیری قطعی از عبور از ماتریس ۶۴/۸۸.

## Gate اجباری قطع عمدی

روی همان سرور و دیسک دائمی اجرا کنید:

```bash
python -m pip install -e '.[research,test]'

ctsteg runtime-gate \
  --output-dir /srv/ctsteg/gates \
  --workers 2 \
  --jobs 8
```

این فرمان یک pool واقعی می‌سازد، پس از ثبت چند checkpoint کل گروه پردازش را
با `SIGKILL` قطع می‌کند، دوباره همان اجرا را بالا می‌آورد و کنترل می‌کند که:

- artefactهای کامل‌شده تغییر نکرده باشند؛
- اجرای دوم آن‌ها را cache-hit تشخیص دهد؛
- lock باقی‌مانده بایگانی شود؛
- تمام کارها تکمیل شوند؛
- checksum تک‌تک فایل‌های بستهٔ دانلودی صحیح باشد.

فایل زیر Gate مورد قبول اجرای اصلی است:

```text
/srv/ctsteg/gates/latest_runtime_gate.json
```

اگر کد runtime تغییر کند، fingerprint عوض می‌شود و گزارش قبلی پذیرفته
نخواهد شد.

## اجرای اصلی یا Resume

```bash
ctsteg digital-research-run \
  --manifest /srv/ctsteg/inputs/traceability-core-v2.csv \
  --config configs/digital_ad/final_locked_v1.toml \
  --stability-profile /srv/ctsteg/inputs/stability-v2.json \
  --runtime-gate-report /srv/ctsteg/gates/latest_runtime_gate.json \
  --output-root /srv/ctsteg/results \
  --cache-dir /srv/ctsteg/cache \
  --workers 0 \
  --minimum-free-disk-gib 100 \
  --require-parquet \
  --engineering-control
```

اجرای دوبارهٔ همین فرمان همان Resume است؛ اشیای کامل دوباره محاسبه نمی‌شوند.
اگر قطع وسط یک جاسازی رخ دهد فقط همان جاسازی تکرار می‌شود. اگر قطع وسط یک
حمله رخ دهد جاسازی و همهٔ حمله‌های کامل‌شده حفظ می‌شوند.

`--workers 0` تعداد worker را با توجه به CPU، RAM آزاد، رزرو سیستم و سقف ۱۶
تعیین می‌کند. برای سرور پیشنهادی `32 vCPU / 64 GB RAM` پیش‌فرض‌ها چهار CPU و
۱۲ گیگ RAM را برای سیستم و I/O کنار می‌گذارند.

پیش از شروع workerها، فضای آزاد هر دو مسیر خروجی و cache کنترل و در
`resource_plan.json` ثبت می‌شود. اگر هرکدام از حد
`--minimum-free-disk-gib` کمتر باشند، اجرا بدون تولید کار جدید متوقف می‌شود.

## پایش زنده و ETA

سرویس monitor بدون تغییر artefactهای علمی، مصرف process tree و پیشرفت
checkpointها را ثبت می‌کند:

```bash
ctsteg research-status \
  --output-root /srv/ctsteg/results \
  --watch
```

این خروجی درصد استفادهٔ الگوریتم از ظرفیت workerهای تخصیص‌یافته، CPU و
`iowait` کل سرور، RAM، I/O، سرعت task در ساعت و ETA را نشان می‌دهد. ETA پس
از ثبت حداقل دو پایان واقعی در مرحلهٔ جاری از throughput همان مرحله استفاده
می‌کند.

راهنمای نصب Ubuntu، MATLAB، toolbox، داده و systemd در
[`SERVER_DEPLOYMENT_FA.md`](SERVER_DEPLOYMENT_FA.md) آمده است.

## محدودیت علمی مهم

این زیرساخت آماده است، اما `--engineering-control` فقط Haar یا proxy را اجرا
می‌کند و خروجی را صریحاً مهندسی برچسب می‌زند. اجرای نهایی علمی PDFB همچنان
نیازمند Adapter واقعی، شواهد Stage-0 و تأیید انسانی transform است.

شرح کامل ساختار فایل‌ها، قواعد hash، triggerهای شرطی و نصب systemd در
[`RUNTIME_EXECUTION_GATE.md`](RUNTIME_EXECUTION_GATE.md) آمده است.
