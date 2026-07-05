# EduSynth — Инструкция по развёртыванию

## Быстрый старт (Docker Compose)

1. Склонируйте репозиторий:
```bash
git clone <repo-url>
cd edusynth
```

2. Скопируйте и заполните переменные окружения:
```bash
cp infra/.env.example infra/.env
# Отредактируйте infra/.env — вставьте ваши API-ключи Yandex Cloud
```

3. Запустите сервисы:
```bash
cd infra
docker compose up -d
```

4. Примигрируйте базу данных:
```bash
docker compose exec backend alembic upgrade head
```

5. Откройте http://localhost

## Переменные окружения

| Переменная | Описание | Пример |
|-----------|----------|--------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://edusynth:pass@postgres:5432/edusynth` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `JWT_SECRET` | Секретный ключ для JWT | `your-super-secret-key` |
| `YANDEX_FOLDER_ID` | ID каталога Yandex Cloud | `b1g...` |
| `YANDEX_API_KEY` | API-ключ сервисного аккаунта | `AQVN...` |
| `S3_ACCESS_KEY` | Access key для Object Storage | |
| `S3_SECRET_KEY` | Secret key для Object Storage | |

## Продакшн деплой

1. Используйте `docker-compose.prod.yml`:
```bash
docker compose -f docker-compose.prod.yml up -d
```

2. Настройте HTTPS (Let's Encrypt):
```bash
certbot certonly --webroot -w /usr/share/nginx/html -d your-domain.ru
```

3. Обновите nginx.conf для HTTPS.

## Yandex Cloud

Для развёртывания на Yandex Cloud:

1. Создайте Managed PostgreSQL кластер
2. Создайте Managed Redis кластер
3. Создайте Object Storage bucket
4. Создайте сервисный аккаунт с ролями:
   - `ai.languageModels.user` (для YandexGPT)
   - `ai.imageGenerator.user` (для YandexART)
   - `storage.editor` (для Object Storage)
5. Создайте API-ключ сервисного аккаунта
6. Развёртывайте Docker на виртуальной машине или в Yandex Cloud Functions
