FROM python:3.11-slim

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/ /app/frontend

ENV FRONTEND_DIR=/app/frontend
ENV PORT=8000

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
