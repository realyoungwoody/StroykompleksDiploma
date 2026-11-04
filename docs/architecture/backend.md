# Backend

Backend — синхронное FastAPI-приложение на Python 3.12, Pydantic v2 и SQLAlchemy 2. Все HTTP endpoints находятся в `backend/app/main.py`; бизнес-логика вынесена в сервисы расчёта, ИИ и структурированного подбора.

## Слои

- `core/config.py` — настройки из переменных окружения и корневого `.env`.
- `core/database.py` — engine, session factory, SQLite foreign keys.
- `core/security.py` — Argon2, подписанная сессия, телефон, origin и rate limit.
- `models.py` — ORM-модели.
- `schemas.py` — входные и выходные контракты.
- `services/pricing.py` — расчёт только по активным услугам.
- `services/selection.py` — версионированное состояние выбранных услуг.
- `services/assistant.py` — retrieval, проверенные действия, LLM и fallback.
- `seed.py` — идемпотентные демоданные.

## Жизненный цикл

`backend/entrypoint.sh` сначала выполняет `alembic upgrade head`, затем запускает Uvicorn на `0.0.0.0:8000`. Startup hook дополнительно вызывает `create_all` и seed; seed создаёт данные только при пустых соответствующих таблицах.

## Ошибки и валидация

Явные `HTTPException` преобразуются в `{ "error": { "code", "message" } }`. Ошибки Pydantic остаются в стандартном поле `detail`; frontend умеет собрать их сообщения. Ограничения количества, длины, формата slug, номера заявки и статусов заданы в схемах.

## Ограничения масштабирования

SQLite и in-memory rate limiter рассчитаны на один backend-процесс демонстрационного проекта. Несколько реплик потребуют внешней БД, распределённого rate limit и общей стратегии миграций. Синхронный HTTP-вызов LLM занимает worker до timeout; для большой нагрузки нужен отдельный пул или очередь.
