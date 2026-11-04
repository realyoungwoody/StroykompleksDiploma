# Docker Compose

Compose запускает `backend` и `web`; profile `local` дополнительно включает `ollama` и `ollama-init`.

## Первый запуск

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Замените в `.env` `ADMIN_PASSWORD` и `SESSION_SECRET`. Для обычного HTTP localhost оставьте `COOKIE_SECURE=false`. Все переменные, значения по умолчанию и примеры трёх LLM-режимов приведены в [справочнике `.env`](environment.md).

Без LLM:

```bash
# в .env: LLM_MODE=demo
docker compose up --build -d
```

С локальной Qwen3:

```bash
docker compose --profile local up --build -d
docker compose --profile local logs -f ollama ollama-init backend
```

Первый local-запуск скачивает модель в `ollama_models`. Сайт: <http://localhost:8080>, Swagger: <http://localhost:8080/api/docs>.

## Проверка

```bash
docker compose ps
./scripts/smoke_test.sh
```

Для local LLM:

```bash
./scripts/check_local_llm.sh
```

## Управление

```bash
docker compose logs --tail=200 backend web
docker compose restart backend
docker compose down
```

При profile local добавляйте `--profile local`. Обычный `down` сохраняет данные и модели.

## Volumes

- `stroykompleks_data` — SQLite;
- `ollama_models` — модели Ollama.

Не используйте `docker compose down -v`, если данные нужны. Полный локальный сброс выполняйте только через `./scripts/reset_demo_data.sh`, который требует подтверждение `RESET`.

## Конфигурация Ollama

По умолчанию: `qwen3:1.7b`, context 4096, keep-alive 5 минут, memory limit 4 GB, CPU limit 4. Порт Ollama только `expose`, поэтому недоступен с host напрямую. Для более крупной модели сначала проверьте RAM.
