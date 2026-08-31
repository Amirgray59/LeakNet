FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# کد پروژه
COPY backend ./backend
COPY frontend ./frontend
COPY training ./training

# پوشه‌های داده و مدل (با volume مونت می‌شوند)
RUN mkdir -p /app/data /app/models

EXPOSE 8000

# اجرای FastAPI + فرانت (استاتیک از همان سرویس)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
