FROM python:3.11-slim

WORKDIR /app

COPY resolver/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY resolver /app

CMD ["python", "app.py"]