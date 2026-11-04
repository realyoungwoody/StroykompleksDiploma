# Переменные окружения и `.env`

Корневой файл `.env` содержит runtime-конфигурацию backend и Docker Compose. Он не входит в Git: в репозитории хранится только безопасный шаблон [`.env.example`](../../.env.example).

## Создание файла

Из корня репозитория:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
chmod 600 .env
```

Замените `ADMIN_PASSWORD` на длинный уникальный пароль, а `SESSION_SECRET` — на результат команды. Не используйте значения шаблона за пределами одноразового локального запуска.

Backend, запущенный непосредственно на host, читает корневой `.env` через Pydantic Settings. Docker Compose передаёт этот же файл контейнеру `backend` через `env_file`. Переменные реального окружения процесса имеют приоритет над `.env` при прямом host-запуске.

## Справочник backend

| Переменная | Обязательность и значение | Пример / значение по умолчанию |
| --- | --- | --- |
| `APP_NAME` | Отображаемое имя приложения. Обычно менять не требуется. | `Стройкомплекс` |
| `ADMIN_EMAIL` | Логин первого администратора. Используется seed только при первом создании записи. | `admin@example.com` |
| `ADMIN_PASSWORD` | Пароль первого администратора. Секрет; задайте длинное уникальное значение до первого запуска. | Встроенное demo-значение нельзя использовать публично. |
| `SESSION_SECRET` | Ключ подписи admin-cookie. Секрет; рекомендуется не менее 32 случайных байт. Смена завершает действующие сессии. | Результат `secrets.token_hex(32)` |
| `DATABASE_URL` | SQLAlchemy URL базы. Для Compose требуется SQLite-файл внутри volume `/data`. | Compose: `sqlite:////data/stroykompleks.sqlite3`; host: `sqlite:///./stroykompleks.sqlite3` |
| `COOKIE_SECURE` | Передавать admin-cookie только по HTTPS. | `false` для HTTP localhost; `true` в production |
| `LLM_MODE` | Режим консультанта: `demo`, `remote` или `local`. | Встроенный default: `demo`; шаблон: `local` |
| `LLM_API_KEY` | Bearer token OpenAI-compatible API. В `local` используется непубличное техническое значение, в `demo` не нужен. | `ollama` для local |
| `LLM_BASE_URL` | Base URL без `/chat/completions`: backend добавляет этот путь сам. | Local: `http://ollama:11434/v1` |
| `LLM_MODEL` | Идентификатор модели у выбранного провайдера. | Local: `qwen3:1.7b` |
| `LLM_TIMEOUT_SECONDS` | Timeout одного HTTP-запроса к модели в секундах. | Backend default: `25`; шаблон local: `120` |
| `LLM_MAX_TOKENS` | Максимальное число токенов ответа модели. | `350` |

`ADMIN_EMAIL` и `ADMIN_PASSWORD` не перезаписывают уже созданного администратора при последующих рестартах. Если SQLite volume существует, смена этих двух строк в `.env` не меняет текущие credentials.

## Настройки локальной Ollama

Эти переменные использует Docker Compose profile `local`, а не Pydantic-конфигурация backend:

| Переменная | Назначение | Значение шаблона |
| --- | --- | --- |
| `OLLAMA_CONTEXT_LENGTH` | Размер контекста модели. | `4096` |
| `OLLAMA_KEEP_ALIVE` | Сколько модель остаётся загруженной после запроса. | `5m` |
| `OLLAMA_MEMORY_LIMIT` | Лимит памяти контейнера Ollama. | `4g` |
| `OLLAMA_CPU_LIMIT` | Лимит CPU контейнера Ollama. | `4.0` |

`LLM_MODEL` одновременно выбирает модель backend и модель, которую скачивает `ollama-init`. Для согласованности меняйте её в `.env`, а не только одноразовой shell-переменной.

## Готовые режимы

### Demo без модели

Расчёты, подбор услуг и кнопки корзины продолжают работать детерминированно; генеративный API не вызывается.

```env
LLM_MODE=demo
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=25
LLM_MAX_TOKENS=350
```

Запуск:

```bash
docker compose up --build -d
```

### Локальная Ollama

```env
LLM_MODE=local
LLM_API_KEY=ollama
LLM_BASE_URL=http://ollama:11434/v1
LLM_MODEL=qwen3:1.7b
LLM_TIMEOUT_SECONDS=120
LLM_MAX_TOKENS=350
```

Запуск:

```bash
docker compose --profile local up --build -d
./scripts/check_local_llm.sh
```

В local-режиме backend намеренно принимает только внутренний host `ollama`; внешний URL не считается локальным провайдером.

### Внешний OpenAI-compatible API

```env
LLM_MODE=remote
LLM_API_KEY=replace-with-provider-token
LLM_BASE_URL=https://provider.example/v1
LLM_MODEL=provider-model-id
LLM_TIMEOUT_SECONDS=25
LLM_MAX_TOKENS=350
```

`LLM_BASE_URL` должен соответствовать документации провайдера. Если его API уже заканчивается на `/v1`, оставьте `/v1`, но не добавляйте `/chat/completions`: приложение делает это автоматически. Не помещайте настоящий token в документацию, issue, PR или commit.

## Production

Deployment ожидает постоянный файл `<DEPLOY_PATH>/shared/.env`. Скрипт создаёт символическую ссылку из каждого release в этот файл, поэтому секреты не входят в git archive и сохраняются между релизами.

Минимальные отличия production:

```env
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=replace-with-unique-long-password
SESSION_SECRET=replace-with-random-64-hex-characters
DATABASE_URL=sqlite:////data/stroykompleks.sqlite3
COOKIE_SECURE=true
LLM_MODE=demo
```

На сервере:

```bash
chmod 600 /opt/stroykompleks/shared/.env
```

Не путайте runtime `.env` с настройками GitHub Environment `production`. В GitHub Secrets находятся SSH-данные деплоя (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`), а в GitHub Variables — `DEPLOY_PORT`, `DEPLOY_PATH`, `PRODUCTION_URL`. Они нужны workflow для подключения к серверу и не заменяют серверный `shared/.env`.

## Проверка конфигурации

Проверить синтаксис Compose без вывода секретов:

```bash
docker compose config --quiet
```

После запуска:

```bash
docker compose ps
curl -fsS http://localhost:8080/api/v1/health
```

Health сообщает выбранный режим, тип провайдера, модель и признак настройки, но не раскрывает API key или base URL. Не публикуйте полный вывод `docker compose config`, `env`, логи HTTP-запросов или сам `.env`: они могут содержать секреты.

## Ротация и устранение ошибок

- Если `LLM_API_KEY`, пароль или ключ сессии попал в чат, screenshot, issue либо commit, отзовите его у источника и создайте новый. Простого удаления текста недостаточно.
- После изменения `.env` пересоздайте затронутый контейнер: `docker compose up -d --force-recreate backend`.
- Если меняется local-модель, запустите Compose с profile `local`, чтобы `ollama-init` проверил её наличие.
- При ошибке SQLite сравните `DATABASE_URL` со способом запуска: `/data/...` предназначен для контейнера, относительный файл — для host.
- Диагностика типичных проблем описана в [руководстве по устранению неполадок](troubleshooting.md).
