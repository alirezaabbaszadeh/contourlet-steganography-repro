# راهنمای مسیر دیجیتال A+D

## مرز علمی

مسیر `DIGITAL_A_D` کاملاً از P0 جدا است و AP/GP/HP را استفاده نمی‌کند. فایل‌های
عددی P0 با Hash Guard در CI محافظت می‌شوند.

دو backend فعلاً قابل اجرا هستند:

- `proxy_directional_lp_v1`: همان proxy جهت‌دار قبلی، فقط برای ممیزی و ردیابی
  مقاله؛ PDFB نویسندگان نیست.
- `haar_orthogonal_control_v1`: کنترل مهندسی ارتونرمال با چهار زیرباند
  256×256؛ برای اجرای دقیق نرم‌افزار C0 تا C3 است، ولی Contourlet نیست.

proxy جهت‌دار با اینکه تصویر را دقیق بازسازی می‌کند، ضرایب مستقلاً قابل‌نوشتن
ندارد. در پایلوت PSNR حدود 45 dB، استخراج Clean آن شکست می‌خورد؛ این شکست
ثبت می‌شود و با کاهش پنهانی PSNR دور زده نمی‌شود.

## روش‌ها

| روش | A | D |
|---|---|---|
| C0_FIXED | خیر | حفاظت متقارن |
| C1_A | تخصیص و قدرت تطبیقی | حفاظت متقارن |
| C2_D | تخصیص ثابت | حفاظت نابرابر |
| C3_A_D | تخصیص و قدرت تطبیقی | حفاظت نابرابر |

هر چهار روش دقیقاً 222,360 بیت payload ناخالص دارند. Secret برابر 128×128
و payload خالص 0.5 bpp است.

## دستورات اصلی

ممیزی Transform:

```bash
ctsteg audit-transform \
  --config configs/digital_ad/proxy_audit_v1.toml \
  --output results/proxy-audit.json
```

اجرای پایلوت:

```bash
ctsteg digital-demo \
  --config configs/digital_ad/stage3_pilot.toml \
  --method C3_A_D \
  --attack-profile pilot \
  --output-dir results/c3-pilot
```

ساخت Stability فقط از Calibration:

```bash
ctsteg digital-calibrate \
  --manifest data/calibration.csv \
  --config configs/digital_ad/format_v1.toml \
  --output results/stability-v1.json
```

Benchmark و تحلیل:

```bash
ctsteg digital-benchmark \
  --manifest data/locked-test.csv \
  --config configs/digital_ad/final_locked_v1.toml \
  --stability-profile results/stability-v1.json \
  --output-dir results/final-v1

ctsteg digital-factorial \
  --results results/final-v1/results_long.csv \
  --output-dir results/factorial-v1
```

## تفسیر نتیجه

- برتری C3 بر C0 اثر کل A+D را می‌سنجد.
- C1 در برابر C0 اثر A را می‌سنجد.
- C2 در برابر C0 اثر D را می‌سنجد.
- عبارت `C3-C2-C1+C0` interaction واقعی A و D را می‌سنجد.

Runهای ناموفق حذف نمی‌شوند. علاوه بر BER شرطی، نرخ شکست، سهم بیت‌های شناخته‌شده
و `effective_unrecovered_bit_rate` گزارش می‌شود. پس از شکست RS یا CRC هیچ
Secret جعلی ساخته نمی‌شود.

برای ادعای مستقیم برتری نسبت به مقاله، هنوز PDFB دقیق یا یک تفسیر MATLAB
تأییدشده لازم است. نتایج backend Haar فقط کنترل مهندسی هستند.
