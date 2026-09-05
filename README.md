# 💧 LeakNet — مکان‌یابی نشتی شبکه آب (نسخه ساده: فقط XGBoost)

## راه‌اندازی

```bash
docker compose up --build -d
# مرورگر → http://localhost:8000
```

مدل XGBoost از قبل روی `a1-bench2-Udata-nd10.xlsx` آموزش داده شده و در `models/` هست.

## آموزش مجدد (اختیاری)

```bash
docker compose exec leaknet python training/train_fast.py
# یا با فایل دیگر:
docker compose exec leaknet env TRAIN_DATA=data/your-file.xlsx python training/train_fast.py
curl -X POST http://localhost:8000/api/models/reload
```

## نحوه استفاده

1. **آپلود فایل اکسل** با ستون‌های `n1 … n31` — اگر چند سطر باشد، **سطر آخر** در پنل سنسورها قرار می‌گیرد.
2. مقادیر سنسورها را می‌توانید **دستی تغییر دهید**.
3. دکمه **«پیش‌بینی نشتی با XGBoost»** → نشتی روی نقشه (مارکر قرمز + لوله قرمز) نمایش داده می‌شود.
4. **پنل نتیجه** باز می‌شود: لوله نشتی‌دار، Lx / Ly / Lz / Emitter، و **دقت مدل (R²)**.

## API

| متد | مسیر | توضیح |
|---|---|---|
| GET | `/api/network` | توپولوژی شبکه |
| GET | `/api/models` | وضعیت و دقت XGBoost |
| POST | `/api/upload-sensors` | آپلود xlsx/csv → سطر آخر n1..n31 |
| POST | `/api/predict` | `{pressures: {n1..n31}}` → محل نشتی |
| POST | `/api/models/reload` | ریلود مدل بعد از آموزش مجدد |
