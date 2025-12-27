FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt

# Устанавливаем временные системные зависимости для сборки C-расширений (если нужны),
# затем устанавливаем Python-зависимости и удаляем сборочные пакеты для уменьшения размера.
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential python3-dev gcc && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    apt-get purge -y --auto-remove build-essential python3-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY . /app

# Точка входа бота
CMD ["python3", "bot.py"]
