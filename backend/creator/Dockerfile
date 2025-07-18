FROM python:3.11-slim

WORKDIR /app

COPY creator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY creator /app

CMD ["python", "app.py"]
