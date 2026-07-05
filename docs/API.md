# EduSynth API Documentation

## Базовый URL

- Локально: `http://localhost:8000`
- Продакшн: `https://your-domain.ru`

## Авторизация

Все защищённые эндпоинты требуют JWT токен в заголовке:
```
Authorization: Bearer <access_token>
```

## Эндпоинты

### Auth

#### POST /api/auth/register
Регистрация нового пользователя.

**Body:**
```json
{
    "email": "user@example.com",
    "password": "password123",
    "full_name": "Иван Иванов"
}
```

**Response (200):**
```json
{
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer"
}
```

#### POST /api/auth/login
Авторизация.

**Body:**
```json
{
    "email": "user@example.com",
    "password": "password123"
}
```

#### POST /api/auth/refresh
Обновление access token.

**Body:**
```json
{
    "refresh_token": "eyJ..."
}
```

#### GET /api/auth/me
Получение текущего пользователя (требует авторизации).

---

### Lessons

#### POST /api/lessons/generate
Генерация урока (или получение из кэша).

**Body:**
```json
{
    "topic": "Обыкновенные дроби",
    "grade": 6,
    "subject": "Математика"
}
```

**Response (200):**
```json
{
    "id": "uuid",
    "topic": "Обыкновенные дроби",
    "grade": 6,
    "subject": "Математика",
    "content": {
        "title": "Обыкновенные дроби",
        "introduction": "...",
        "main_content": "<p>...</p>",
        "examples": ["..."],
        "key_points": ["..."],
        "quiz": [
            {
                "question": "...",
                "options": ["A", "B", "C", "D"],
                "correct_index": 0,
                "explanation": "..."
            }
        ]
    },
    "image_urls": ["https://..."],
    "created_at": "2026-06-25T...",
    "views_count": 1
}
```

#### GET /api/lessons/{lesson_id}
Получение урока по ID.

#### GET /api/lessons/history/
История уроков пользователя (последние 50).

---

### Quiz

#### POST /api/quiz/check
Проверка ответов на тест.

**Body:**
```json
{
    "lesson_id": "uuid",
    "answers": [0, 2, 1, 3]
}
```

**Response (200):**
```json
{
    "total": 4,
    "correct": 3,
    "score_percent": 75,
    "results": [
        {
            "question": "...",
            "selected": 0,
            "correct": 0,
            "is_correct": true,
            "explanation": "..."
        }
    ]
}
```

---

### Dashboard

#### GET /api/dashboard/stats
Статистика пользователя.

**Response (200):**
```json
{
    "total_lessons": 15,
    "completed": 10,
    "average_score": 78,
    "subject_breakdown": {
        "Математика": 8,
        "Физика": 4,
        "Химия": 3
    },
    "subscription": {
        "status": "free",
        "expires_at": null
    }
}
```

---

## Health Check

#### GET /health
```json
{
    "status": "healthy",
    "version": "1.0.0"
}
```

---

## Ошибки

| Код | Описание |
|-----|----------|
| 400 | Невалидный запрос |
| 401 | Не авторизован |
| 404 | Не найдено |
| 409 | Конфликт (email уже зарегистрирован) |
| 502 | Ошибка внешнего сервиса (Yandex AI) |

## Swagger UI

Интерактивная документация доступна по адресу: `http://localhost:8000/docs`
