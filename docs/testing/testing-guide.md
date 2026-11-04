# Руководство по тестированию

## Backend

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/ruff check app tests
../.venv/bin/pytest -q
```

Тесты используют временную SQLite и очищают cached settings/modules через fixtures. Покрываются каталог, расчёты, заявки, idempotency, tracking, admin auth/CRUD/metrics, LLM fallback/actions и selection.

Текущее контрольное состояние на 4 ноября 2026 после security regression-тестов: Ruff PASS, `200 passed`; остаются два предупреждения FastAPI о deprecated `on_event`.

## Frontend

```bash
cd frontend
npm ci
npm run typecheck
npm test
npm run build
```

Vitest + Testing Library проверяют ключевые UI-сценарии, включая уведомления, корзину и ИИ-действия. Текущее контрольное состояние: `22 passed`, TypeScript и production build PASS.

Если host Node недоступен, используйте чистый build stage:

```bash
docker build --target build -t stroykompleks-frontend-test ./frontend
docker run --rm stroykompleks-frontend-test npm run typecheck
docker run --rm stroykompleks-frontend-test npm test
```

## Docker smoke

```bash
docker compose config --quiet
LLM_MODEL=qwen3:1.7b docker compose --profile local config --quiet
docker compose up -d --build
./scripts/smoke_test.sh
docker compose ps
```

Ожидается HTTP 200 для health, services и Swagger; backend и web должны стать healthy. Smoke не удаляет данные.

## Ручная проверка

1. Каталог → две услуги → изменение объёма → серверный total.
2. Оформление → повтор клика не создаёт дубль → сохранение номера.
3. Tracking с правильным и неверным телефоном.
4. Admin login → поиск → status/note → history.
5. Создание/редактирование/deactivation услуги.
6. Клиентский ИИ: несколько услуг и площади → видимые кнопки → проверенное добавление.
7. Недоступная LLM → предупреждение и рабочий demo fallback.
8. Mobile navigation, focus, keyboard и отсутствие horizontal overflow.

## CI parity

CI выполняет те же backend/frontend команды и полный Compose smoke в `LLM_MODE=demo`. Локальный PASS не заменяет GitHub checks, особенно после изменения Docker, workflow, lock-файлов или зависимостей.
