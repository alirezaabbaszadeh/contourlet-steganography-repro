# راهنمای استقرار کامل سرور اوبونتو

## نتیجهٔ مورد انتظار

پس از یک‌بار دسترسی مدیریتی، سرور برای commit دقیق پروژه آماده می‌شود:

- Ubuntu، CPU، AVX2، RAM، دیسک، sudo و اینترنت ابتدا بدون تغییر بررسی می‌شوند؛
- Python 3.12 مستقل از Python پیش‌فرض اوبونتو نصب می‌شود؛
- MATLAB R2026a با ابزار رسمی MPM نصب می‌شود؛
- آرشیو Contourlet Toolbox فقط با SHA-256 صحیح نصب می‌شود؛
- داده‌های کاندید USC-SIPI از قبل دانلود و اعتبارسنجی می‌شوند؛
- همهٔ تست‌ها و Gate واقعی `SIGKILL` اجرا می‌شوند؛
- پس از reboot همان اجرا به‌صورت خودکار Resume می‌شود؛
- مصرف CPU/RAM/I/O، سرعت واقعی و ETA زنده قابل مشاهده است.

این آماده‌سازی به‌تنهایی به معنی تأیید علمی PDFB، انتخاب چهار زوج نهایی یا
فعال‌شدن لایسنس MATLAB نیست.

## مشخصات هدف

```text
Ubuntu 22.04 LTS یا 24.04 LTS
x86-64 با AVX2
حداقل: 16 CPU منطقی، 32 GiB RAM، 250 GiB فضای دائمی آزاد
پیشنهادی: 32 CPU منطقی، 64 GiB RAM، 500 GiB NVMe آزاد
```

طبق الزامات رسمی R2026a، هر دو نسخهٔ Ubuntu پشتیبانی می‌شوند، AVX2 توصیه شده
و SSD قویاً توصیه شده است:

<https://www.mathworks.com/support/requirements/matlab-linux.html>

موازی‌سازی ماتریس ۶۴/۸۸ توسط Python انجام می‌شود؛ بنابراین روی یک سرور،
Parallel Computing Toolbox برای این پروژه لازم نیست. در وضعیت فعلی Stage-0
فقط خود MATLAB و Contourlet Toolbox خارجی را نیاز دارد؛ مسیر قدیمی
`matlab/run_pair.m` نیز از Image Processing Toolbox استفاده می‌کند، پس نصب
پیش‌فرض هر دو محصول MathWorks را آماده می‌کند.

## چیزهایی که نباید ارسال شوند

کلید خصوصی SSH، GitHub Token، رمز MathWorks، کلید لایسنس و File Installation
Key را در چت، Git، فایل `server.env` یا خط فرمان قرار ندهید.

برای اتصال، یک کلید عمومی موقت به سرور اضافه می‌شود. لایسنس شبکه‌ای MATLAB
باید در یک فایل فقط‌خواندنی مانند
`/etc/ctsteg-credentials/network.lic` یا از طریق آدرس مجاز
`MLM_LICENSE_FILE` تنظیم شود. لایسنس شخصی ممکن است یک فعال‌سازی یک‌بارهٔ
جداگانه بخواهد.

نصب MATLAB با فعال‌بودن لایسنس یکی نیست؛ bootstrap باینری‌ها را آماده می‌کند
ولی تا اجرای موفق `matlab -batch` ادعای فعال‌بودن MATLAB نمی‌کند.

## Contourlet Toolbox

نسخهٔ ۱٫۰٫۰٫۰ از File Exchange 8837 داخل مخزن بازتوزیع نمی‌شود:

<https://www.mathworks.com/matlabcentral/fileexchange/8837-contourlet-toolbox>

پس از پذیرش شرایط منبع، فایل را روی سرور بگذارید:

```text
/srv/ctsteg/bootstrap/contourlet_toolbox.zip
```

و hash آن را محاسبه کنید:

```bash
sha256sum /srv/ctsteg/bootstrap/contourlet_toolbox.zip
```

نصاب hash را اجباری کنترل می‌کند و وجود هم‌زمان `pdfbdec.m` و `pdfbrec.m`
را بررسی می‌کند.

## نصب یک‌باره

```bash
sudo install -m 0600 \
  deploy/bootstrap/server.env.example \
  /etc/ctsteg-bootstrap.env

sudoedit /etc/ctsteg-bootstrap.env
```

مقدار `CTSTEG_GIT_REF` باید SHA کامل ۴۰ کاراکتری commit باشد. استفاده از
branch شناور به‌صورت پیش‌فرض رد می‌شود تا reboot باعث تغییر خاموش کد نشود.

بررسی فقط‌خواندنی:

```bash
./scripts/bootstrap_ubuntu_server.sh \
  --check \
  --config /etc/ctsteg-bootstrap.env
```

اگر خروجی `ready=true` بود:

```bash
sudo ./scripts/bootstrap_ubuntu_server.sh \
  --apply \
  --config /etc/ctsteg-bootstrap.env
```

بررسی نهایی بدون تغییر:

```bash
sudo /usr/local/sbin/ctsteg-bootstrap \
  --verify \
  --config /etc/ctsteg-bootstrap.env
```

هر commit در پوشهٔ جداگانهٔ زیر نصب می‌شود:

```text
/opt/ctsteg/releases/<commit>
```

لینک `current` فقط پس از موفقیت نصب و تست جابه‌جا می‌شود.

## سیاست تلاش مجدد و شکست

عملیات موقت با backoff نمایی، ثبت attempt و سقف مشخص تکرار می‌شوند:

- نصب بسته‌ها، Git، Python و دانلودها: حداکثر ۸ تلاش؛
- هر مقصد HTTPS در preflight: حداکثر ۴ تلاش به‌صورت موازی؛
- Gate واقعی قطع `SIGKILL` و Resume: حداکثر ۳ اجرای مستقل؛
- شکست عملیاتی اجرای پژوهش: حداکثر ۱۲ start در یک ساعت؛
- شکست موقت bootstrap هنگام boot: حداکثر ۱۲ start در ۲۴ ساعت.

مقادیر پیش‌فرض با متغیرهای `CTSTEG_RETRY_*`،
`CTSTEG_NETWORK_CHECK_*` و `CTSTEG_RUNTIME_GATE_ATTEMPTS` در
`deploy/bootstrap/server.env.example` قابل تنظیم‌اند.

این سقف‌ها عمدی‌اند. خروج `2` برای مانع علمی/محیطی و خروج `64` برای خطای
پیکربندی یا یکپارچگی restart نمی‌شوند. بنابراین checksum اشتباه، لایسنس
ناموجود، manifest نامعتبر یا Gate علمی مردود پشت حلقهٔ بی‌نهایت پنهان
نمی‌شوند. سابقهٔ هر attempt در journal یا پوشهٔ attempt اجرای runtime باقی
می‌ماند.

## رفتار نصب MATLAB

آخرین MPM رسمی از این آدرس دریافت می‌شود:

```text
https://www.mathworks.com/mpm/glnxa64/mpm
```

وابستگی‌های دقیق release/Ubuntu از مخزن مرجع MathWorks خوانده می‌شوند و نصب
پیش‌فرض این است:

```text
mpm install --release=R2026a \
  --destination=/opt/matlab/R2026a \
  --products=MATLAB Image_Processing_Toolbox
```

MPM محصول نصب‌شده را دوباره نصب نمی‌کند. نسخه و SHA-256 خود MPM در
`/srv/ctsteg/provenance` ثبت می‌شود.

مراجع رسمی:

- <https://www.mathworks.com/help/install/ug/get-mpm-os-command-line.html>
- <https://www.mathworks.com/help/install/ug/mpminstall.html>

## داده‌ها

فعال‌بودن `CTSTEG_PREFETCH_USC_SIPI=1` تصاویر کاندید را در مسیر زیر آماده
می‌کند:

```text
/srv/ctsteg/data/usc_sipi
```

فایل معتبر موجود دوباره دانلود نمی‌شود. این مرحله «Jet» مبهم مقاله را تعیین
نمی‌کند، زوج cover-secret نمی‌سازد و manifest چهارردیفی نهایی را قفل نمی‌کند.

## ادامهٔ خودکار پس از روشن‌شدن

سه واحد systemd وجود دارد:

```text
ctsteg-bootstrap.service
ctsteg-monitor@final.service
ctsteg-research@final.service
```

ترتیب boot:

1. شبکه و دیسک دائمی آماده می‌شوند؛
2. bootstrap ابتدا همان commit و Gate را سریع اعتبارسنجی می‌کند و فقط در
   صورت نقص وارد نصب/ترمیم idempotent می‌شود؛
3. monitor بالا می‌آید؛
4. فرمان idempotent پژوهش اجرا می‌شود؛
5. همهٔ checkpointهای کامل cache-hit می‌شوند و فقط کار ناتمام تکرار می‌شود.

شکست عملیاتی با retry محدود ادامه می‌یابد؛ مانع علمی یا پیکربندی دائمی با
کدهای `2` و `64` متوقف می‌شود تا اصلاح انسانی انجام شود.

تا قبل از PDFB Adapter تأییدشده، manifest چهارردیفی و stability profile،
مقدار زیر باید صفر بماند:

```text
CTSTEG_ENABLE_RESEARCH_SERVICE=0
```

زیرساخت خودکار اجازه ندارد Gate علمی را دور بزند.

## مشاهدهٔ مصرف منابع و ETA

خروجی زنده:

```text
/srv/ctsteg/monitor/latest.json
/srv/ctsteg/monitor/samples.jsonl
```

تاریخچه هر روز rotate و فشرده می‌شود و ۳۰ نسخه نگهداری می‌شود.
`latest.json` همیشه snapshot اتمیک جاری است.

نمایش یک‌باره:

```bash
/opt/ctsteg/current/venv/bin/ctsteg research-status \
  --output-root /srv/ctsteg/results
```

نمایش زنده:

```bash
/opt/ctsteg/current/venv/bin/ctsteg research-status \
  --output-root /srv/ctsteg/results \
  --watch \
  --interval-seconds 5
```

خروجی JSON:

```bash
/opt/ctsteg/current/venv/bin/ctsteg research-status \
  --output-root /srv/ctsteg/results \
  --json
```

وضعیت این موارد را جدا نشان می‌دهد:

- CPU خود الگوریتم در واحد یک هسته؛
- درصد استفاده از ظرفیت workerهای تخصیص‌یافته؛
- CPU کل سرور و `iowait`؛
- RAM process tree و فشار حافظهٔ کل سرور؛
- سرعت خواندن/نوشتن و فضای آزاد؛
- پیشرفت اجباری ۶۴، تعداد نهایی پس از trigger و سقف ۸۸؛
- task در ساعت و زمان تقریبی پایان.

تا قبل از داشتن نمونهٔ زمانی کافی، ETA برابر `warming up` است. پس از حداقل
دو پایان واقعی در مرحلهٔ جاری، سرعت واقعی همان مرحله مبنا می‌شود. برآورد
مرحلهٔ بعد از میانهٔ زمان checkpointهای کامل استفاده می‌کند و سطح اطمینان
را صریح نشان می‌دهد.

`using_allocated_cpu` یعنی الگوریتم حداقل ۸۵٪ ظرفیت CPU مجاز workerها را مصرف
می‌کند. `io_wait_limited` و `memory_pressure` علت کم‌بودن منطقی CPU را نشان
می‌دهند.

telemetry زنده بیرون پوشهٔ run نوشته می‌شود؛ بنابراین hash اشیای علمی،
checksum بسته و archive را تغییر نمی‌دهد.

## دستورات عملیاتی

```bash
sudo systemctl status ctsteg-bootstrap.service
sudo systemctl status ctsteg-monitor@final.service
sudo systemctl status ctsteg-research@final.service

sudo journalctl -u ctsteg-bootstrap.service -n 200 --no-pager
sudo journalctl -u ctsteg-monitor@final.service -f
sudo journalctl -u ctsteg-research@final.service -f
```

پس از قفل‌شدن ورودی‌ها:

```bash
sudo systemctl enable --now ctsteg-research@final.service
```

## اگر sudo نداشتیم

preflight دقیقاً نشان می‌دهد کاربر root است، passwordless sudo دارد، sudo
رمزدار دارد یا اصلاً sudo ندارد.

برای اجرای واقعی هنگام boot، ایجاد کاربر سرویس، نصب وابستگی‌های Ubuntu و
MATLAB و حفاظت مسیرهای `/opt` و `/srv` یک اقدام مدیریتی لازم است. بدون آن
می‌توان نصب کاربری انجام داد، ولی معادل قابل‌اعتماد سرویس boot نیست؛ به همین
دلیل bootstrap در این حالت fail-closed می‌شود.

## مرز GitHub

bootstrap فقط commit عمومی را می‌خواند و GitHub Token نوشتنی ذخیره نمی‌کند.
ارسال کد، گزارش‌ها و archive سنگین به GitHub یک مرحلهٔ جدا و قابل‌بازبینی
پس از اعتبارسنجی checksum خواهد بود.
