# Локальная разработка

Для полного запуска рекомендуется Docker. Режим без контейнеров удобен для быстрых тестов кода.

## Требования

- Python 3.12;
- Node.js 22 и npm 10+;
- Docker Desktop/Engine с Compose plugin — для интеграционной проверки;
- Git.

## Получение проекта и окружение

```bash
git clone https://github.com/realyoungwoody/StroykompleksDiploma.git
cd StroykompleksDiploma
git switch dev
cp .env.example .env
```

Замените демонстрационные `ADMIN_PASSWORD` и `SESSION_SECRET`. Полный Compose-запуск, база, seed, logs и local LLM описаны в [Docker-инструкции](docker.md).

## Backend

Из корня репозитория:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/uvicorn app.main:app --reload --port 8000
```

Для host-запуска установите `DATABASE_URL=sqlite:///./stroykompleks.sqlite3`. Значение из Docker-примера `/data/...` вне контейнера обычно не подходит. Alembic создаёт схему, а startup seed добавляет демоданные при первом запуске.

## Frontend

В другом терминале:

```bash
cd frontend
npm ci
npm run dev
```

Vite слушает `0.0.0.0:5173` и проксирует `/api` на `http://localhost:8000`. Откройте <http://localhost:5173>.

## Рекомендуемый demo-режим

Для разработки без внешней сети:

```env
LLM_MODE=demo
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

Он сохраняет каталог, расчёты, selection и кнопки корзины; меняется только генеративная формулировка.

## Перед commit

Выполните команды из [руководства по тестированию](../testing/testing-guide.md). Не коммитьте `.env`, SQLite, `node_modules`, `dist` или test artifacts.
