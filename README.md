# 💧 LeakNet — مکان‌یابی نشتی شبکه آب
سامانه وب برای نمایش شماتیک شبکه آب ۳۲ گرهی و مکان‌یابی نشتی لوله‌ها با
مدل‌های یادگیری ماشین (Random Forest · XGBoost · MLP · SVR).

## معماری

```
leaknet/
├── backend/
│   ├── main.py              # FastAPI (API + سرو فرانت)
│   ├── network_topology.py  # توپولوژی شبکه (گره‌ها، لوله‌ها، مختصات)
│   └── model_service.py     # بارگذاری مدل‌ها و پیش‌بینی
├── frontend/
│   ├── index.html           # رابط کاربری (فارسی، RTL)
│   ├── style.css
│   └── app.js               # نقشه SVG تعاملی + اتصال به API
├── training/
│   └── train_all.py         # آموزش یکپارچه ۴ مدل با GridSearchCV
├── data/                    # دیتاست‌های xlsx (volume)
├── models/                  # مدل‌های pkl آموزش‌دیده (volume)
├── Dockerfile
└── docker-compose.yml
```

## ورودی/خروجی مدل‌ها

- **ورودی (X):** فشار گره‌ها `n1 … n31` (ستون ۵ به بعد اکسل)
- **خروجی (y):** `Lx, Ly, Lz, Emitter` (۴ ستون اول اکسل)
- هر مدل → ۴ رگرسور جدا + یک `StandardScaler`

## راه‌اندازی با Docker

```bash
# ۱) دیتاست آموزشی را در data/ بگذارید
cp a1-bench2-Udata-nd2.xlsx data/

# ۲) ساخت و اجرا
docker compose up --build -d

# ۳) آموزش مدل‌ها داخل کانتینر
docker compose exec leaknet python training/train_all.py \
    --data data/a1-bench2-Udata-nd2.xlsx --models rfr,xgboost,mlp,svr

# ۴) ریلود مدل‌ها بدون ری‌استارت
curl -X POST http://localhost:8000/api/models/reload
```

سپس مرورگر: **http://localhost:8000**

> بدون مدل آموزش‌دیده هم سایت بالا می‌آید و در «حالت دمو» پیش‌بینی تقریبی
> (مرکز ثقل افت فشار) انجام می‌شود.

## راه‌اندازی بدون Docker

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
# آموزش:
python training/train_all.py --data data/your-dataset.xlsx --models rfr,xgboost
```

## API

| متد | مسیر | توضیح |
|---|---|---|
| GET | `/api/network` | توپولوژی شبکه (گره/لوله/مختصات) |
| GET | `/api/models` | مدل‌های موجود + معیارهای R²/MSE |
| POST | `/api/predict` | `{pressures, model}` → محل نشتی + نزدیک‌ترین لوله |
| POST | `/api/predict-file` | آپلود xlsx/csv → پیش‌بینی گروهی |
| GET | `/api/sample-real` | نمونه تصادفی از داده واقعی |
| POST | `/api/models/reload` | بارگذاری مجدد مدل‌ها پس از آموزش |
| GET | `/docs` | مستندات Swagger |

## قابلیت‌های فرانت

- نقشه SVG شماتیک شبکه مطابق شکل مقاله (۳۲ گره، ۳۴ لوله، مخزن ۱۰۰m)
- ورود دستی فشار سنسورها یا نمونه واقعی تصادفی
- نمایش نشتی با مارکر قرمز چشمک‌زن + قرمز شدن لوله نشتی‌دار
- مقایسه هم‌زمان ۴ مدل + Ensemble
- آپلود فایل اکسل → نمایش همه نشتی‌ها روی نقشه
- نمایش دقت (R²) مدل‌ها پس از آموزش
