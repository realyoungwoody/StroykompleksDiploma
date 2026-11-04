# Стройкомплекс

Учебная демонстрационная веб-система для цифровизации потока строительных заявок: каталог → серверный расчёт → оформление → обработка администратором → отслеживание статуса.

> Это не официальный сайт предприятия. Цены, пользователи и заявки демонстрационные; оплаты, SMS, 1С и коммерческих обязательств нет.

## Возможности

- каталог и карточки услуг, корзина в браузере и серверный расчёт;
- заявка без регистрации с idempotency-защитой и публичным номером;
- безопасная проверка статуса по номеру и телефону;
- admin-панель: очередь, поиск, статусы, заметки, история, метрики и каталог;
- клиентский ИИ-подбор с гарантированными структурированными кнопками корзины;
- remote OpenAI-compatible LLM, локальная Qwen3 через Ollama или автономный demo fallback;
- Docker Compose, Alembic, CI, CodeQL и проверяемый production deploy с rollback.

## Стек

React 18, TypeScript, Vite, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite, Nginx, Docker Compose. Тесты: pytest, Ruff, Vitest, Testing Library и TypeScript.

```text
Browser → Nginx :8080 → React SPA
                      └→ /api → FastAPI → SQLAlchemy → SQLite
                                      └→ remote LLM / Ollama / demo fallback
```

Backend — единственный источник цен и статусов. LLM формулирует ответ, но не изменяет корзину или заявки.

## Быстрый запуск

Требуются Docker и Docker Compose.

```bash
cp .env.example .env
```

Замените `ADMIN_PASSWORD` и `SESSION_SECRET`. Полное описание всех значений и готовых режимов находится в [справочнике `.env`](docs/deployment/environment.md). Для запуска без модели установите в `.env` `LLM_MODE=demo`, затем:

```bash
docker compose up --build -d
./scripts/smoke_test.sh
```

С локальной Qwen3:

```bash
docker compose --profile local up --build -d
./scripts/check_local_llm.sh
```

- сайт: <http://localhost:8080>
- admin: <http://localhost:8080/admin>
- Swagger: <http://localhost:8080/api/docs>
- health: <http://localhost:8080/api/v1/health>

Остановка без удаления данных: `docker compose down`. Не добавляйте `-v`, если нужно сохранить SQLite и модели.

## Проверки

```bash
cd backend
../.venv/bin/ruff check app tests
../.venv/bin/pytest -q

cd ../frontend
npm ci
npm run typecheck
npm test
npm run build
```

Полная Docker-проверка:

```bash
docker compose config --quiet
docker compose up -d --build
./scripts/smoke_test.sh
docker compose ps
```

## Документация

Полный индекс: **[docs/README.md](docs/README.md)**.

- [Архитектура](docs/architecture/overview.md) и [диаграммы](docs/architecture/diagrams.md)
- [Функциональные возможности](docs/features/catalog.md)
- [ИИ-помощники и кнопки корзины](docs/features/ai-assistants.md)
- [API endpoints](docs/api/endpoints.md)
- [Переменные окружения и `.env`](docs/deployment/environment.md), [Docker](docs/deployment/docker.md), [production](docs/deployment/production.md), [CI/CD](docs/deployment/cicd.md)
- [Безопасность](docs/security/security-overview.md) и [тестирование](docs/testing/testing-guide.md)
- [Contributing](docs/development/contributing.md) и [структура проекта](docs/development/project-structure.md)

## Ограничения MVP

SQLite и in-memory rate limit рассчитаны на один backend. Нет оплаты, CRM/1С, уведомлений, клиентских аккаунтов, MFA и подтверждённого производственного экономического эффекта. Перед реальной эксплуатацией необходимы HTTPS, secure cookies, внешний backup, privacy/legal review и отдельный security audit.
