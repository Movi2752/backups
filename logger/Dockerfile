FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаем директории для логов
RUN mkdir -p /app/logs

EXPOSE 5000

CMD ["python", "app.py"]