# Стройкомплекс — цифровой сервис строительных и отделочных услуг

Учебный демонстрационный MVP для выпускной квалификационной работы о повышении экономической эффективности ООО «Стройкомплекс» с применением принципов Lean Production. Система переводит клиентское обращение в прозрачный поток: выбор услуг → серверный расчёт → регистрация → обработка администратором → отслеживание статуса.

> Проект не является официальным сайтом предприятия. Цены, заявки и пользователи демонстрационные; платежи, SMS и коммерческие обязательства отсутствуют.

## Возможности

- публичный каталог из 8 услуг, поиск и фильтр категорий;
- карточки услуг, корзина в `localStorage`, серверный расчёт актуальной цены;
- оформление заявки без регистрации, защита от повторной отправки;
- проверка статуса по непредсказуемому номеру и нормализованному телефону;
- административный вход через HttpOnly cookie;
- поиск, фильтрация, просмотр, заметки и история смены статуса;
- создание, редактирование, активация и деактивация услуг;
- агрегированные метрики и контроль новых заявок старше 24 часов;
- клиентский помощник и административная read-only сводка;
- OpenAI-compatible LLM и автономный детерминированный demo fallback;
- идемпотентный seed: 8 услуг, 12 FAQ, 11 заявок и администратор.

## Технологии и архитектура

- Frontend: React 18, TypeScript, Vite, React Router, Lucide, CSS.
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic.
- Данные: SQLite в постоянном Docker volume.
- Проверки: pytest, Ruff, Vitest, Testing Library, TypeScript.
- Запуск: Docker Compose, Nginx как единственная публичная точка входа.

```text
Browser → Nginx :8080 → React
                      └→ /api → FastAPI → SQLAlchemy → SQLite volume
                                      └→ Retrieval/Tools → Ollama / внешний LLM / Demo
```

Backend — единственный источник цен, статусов и расчётов. Историческая цена фиксируется в позициях заявки. ИИ изолирован от создания и изменения заявок.

## Запуск

Требуются Docker и Docker Compose.

```bash
cp .env.example .env
```

В `.env` задайте безопасные `ADMIN_PASSWORD` и `SESSION_SECRET` (например, результат `python -c "import secrets; print(secrets.token_hex(32))"`). Для локального HTTP оставьте `COOKIE_SECURE=false`.

Локальная LLM включена в `.env.example`. Первый запуск скачивает Qwen3 в отдельный
persistent volume и может занять несколько минут:

```bash
docker compose --profile local up --build -d
docker compose --profile local logs -f ollama ollama-init backend
```

Адреса:

- сайт: <http://localhost:8080>
- панель: <http://localhost:8080/admin>
- Swagger: <http://localhost:8080/api/docs>
- health: <http://localhost:8080/api/v1/health>

Остановка без удаления данных:

```bash
docker compose --profile local down
```

Первый запуск автоматически применяет миграцию и идемпотентно добавляет демоданные. Учётные данные администратора берутся из локального `.env` и не выводятся в интерфейсе или документации.

Полный сброс (удаляет данные и требует явного ввода `RESET`):

```bash
./scripts/reset_demo_data.sh
```

## ИИ-помощники и локальная Qwen3

Цены, услуги, количество, корзина и статусы всегда определяет FastAPI. LLM только
формулирует короткое объяснение. FAQ, каталог и расчёты не требуют генеративной
модели, поэтому отказ Ollama не останавливает сайт: пользователь получает
детерминированный demo-ответ.

### LOCAL — Ollama без внешних запросов

Безопасная конфигурация для VPS с неизвестным объёмом памяти использует
`qwen3:1.7b` (около 1,4 ГБ файлов модели). Для неё рекомендуется не менее 4 ГБ
свободной RAM и 2 CPU; лимит контейнера по умолчанию — 4 ГБ и 4 CPU. Контекст
ограничен 4096 токенами, параллелизм — одним запросом, ответ — 350 токенами.

```env
LLM_MODE=local
LLM_BASE_URL=http://ollama:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen3:1.7b
LLM_TIMEOUT_SECONDS=120
LLM_MAX_TOKENS=350
OLLAMA_CONTEXT_LENGTH=4096
OLLAMA_KEEP_ALIVE=5m
OLLAMA_MEMORY_LIMIT=4g
OLLAMA_CPU_LIMIT=4.0
```

Запуск:

```bash
docker compose --profile local up --build -d
docker compose --profile local ps
./scripts/check_local_llm.sh
```

`ollama` доступна только во внутренней Docker-сети: порт 11434 не публикуется.
`ollama-init` ждёт HTTP-сервис, проверяет модель, при необходимости выполняет
`ollama pull`, затем делает тестовую генерацию. Модели сохраняются в volume
`ollama_models`; обычные `down`, перезапуск и новый release их не удаляют.

Для замены модели измените `LLM_MODEL`. `qwen3:4b` требует больше RAM, поэтому
перед переключением проверьте сервер. Повторный запуск init-сервиса:

```bash
docker compose --profile local up ollama-init
```

### REMOTE и DEMO

Внешний OpenAI-compatible провайдер используется только при явном режиме
`remote` (старые `auto` и `llm` сохранены для совместимости):

```env
LLM_MODE=remote
LLM_API_KEY=replace-with-provider-key
LLM_BASE_URL=https://provider.example/v1
LLM_MODEL=model-name
LLM_TIMEOUT_SECONDS=25
```

Для полностью детерминированной работы без любой LLM:

```env
LLM_MODE=demo
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

В `local` backend принимает только внутренний адрес `http://ollama/...` и не
может незаметно обратиться к Gemini. Внешние ключи не передаются в Ollama.

### Диагностика и восстановление

```bash
docker compose --profile local ps
docker compose --profile local logs --tail=200 ollama ollama-init backend
docker compose --profile local exec ollama ollama list
docker stats --no-stream
./scripts/check_local_llm.sh
```

Публичный `/api/v1/health` показывает выбранный режим, тип провайдера и модель,
но не URL и не ключ. Время завершившейся генерации записывается в backend-лог без
текста запроса и секретов.

Если первая загрузка оборвалась, не удаляйте volume: повторите запуск
`ollama-init`, и Ollama продолжит/повторит загрузку. Для полного удаления модели
нужно отдельное осознанное удаление volume; deploy и rollback этого не делают.
Если памяти недостаточно, уменьшите `OLLAMA_CONTEXT_LENGTH`, оставьте
`qwen3:1.7b` и проверьте `docker stats`. Не повышайте memory limit сверх реально
доступной RAM VPS.

## Проверки

Backend:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/ruff check app tests
../.venv/bin/pytest -q
```

Frontend (зависимости зафиксированы в `package-lock.json`):

```bash
cd frontend
npm ci
npm run typecheck
npm test
npm run build
```

После Docker-запуска:

```bash
./scripts/smoke_test.sh
```

## Сценарий демонстрации на защите (5–7 минут)

1. Открыть главную и кратко показать цифровой Lean-поток.
2. Добавить 20 м² механизированной штукатурки и 10 м² водоэмульсионной покраски.
3. Показать backend-расчёт **19 200 ₽**.
4. Оформить заявку с явно тестовым телефоном и сохранить номер.
5. Проверить исходный статус «Новая».
6. Войти в `/admin`, найти заявку, добавить заметку и перевести её «В работу».
7. Повторить клиентскую проверку и показать обновлённый статус.
8. Спросить клиентского помощника: «Сколько стоит 20 м² механизированной штукатурки?» — ожидается **15 000 ₽** при исходной цене.
9. Открыть административную ИИ-сводку и показать агрегаты без персональных данных.
10. Объяснить, что стандартизация обращения уменьшает повторный ввод и ожидание, но пример экономии — сценарный, не фактический производственный результат.

## Верификация, ограничения и HTTPS

Фактические результаты, трассируемость и исправленные дефекты находятся в [docs/VERIFICATION_VALIDATION.md](docs/VERIFICATION_VALIDATION.md).

Настройка GitHub Actions, веток `dev`/`main`, production-сервера, секретов, автоматического развёртывания и rollback описана в [docs/CI_CD.md](docs/CI_CD.md).

Ограничения MVP: нет оплаты, CRM/1С, уведомлений, клиентских аккаунтов и подтверждённого производственного экономического эффекта; keyword retrieval не является семантическим поиском; rate limit хранится в памяти процесса. Для публичного размещения необходим HTTPS reverse proxy, `COOKIE_SECURE=true`, сильные секреты, политика резервного копирования и дополнительный security review.

