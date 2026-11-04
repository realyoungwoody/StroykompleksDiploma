# ИИ-помощники

Проект поддерживает клиентского консультанта и административную read-only сводку. Критические решения остаются детерминированными: LLM не создаёт заявку, не меняет статус, не назначает цену и не пишет напрямую в корзину.

## Режимы

| `LLM_MODE` | Поведение |
| --- | --- |
| `demo` | только встроенный детерминированный ответ |
| `remote` | внешний OpenAI-compatible `/chat/completions`; при ошибке fallback |
| `local` | только внутренний `http://ollama/...`; при ошибке fallback |

Устаревшие значения `auto` и `llm` трактуются как внешний режим для совместимости. Для активной LLM обязательны base URL, model и API key; в local разрешён только host `ollama`.

## Клиентский подбор

Backend восстанавливает версионированный `selection`, распознаёт тип работы, вариант услуги, количество и заметку. Позиция получает состояние `incomplete`, `ready`, `invalid` или `added`. Готовые позиции рассчитываются по БД и превращаются в проверенные `cart_actions` независимо от текста LLM.

Если данных не хватает, backend перечисляет недостающие параметры. Если расчёт готов, кнопки появляются из структурированного ответа. Поэтому фраза модели «нажмите кнопку» сама по себе ничего не создаёт и не может скрыть готовое серверное действие.

Frontend сохраняет selection и conversation id в `localStorage`. В запрос передаются последние шесть сообщений, текущая корзина, подтверждённые действия и selection; backend не доверяет присланным service id без проверки каталога.

Пример запроса после уточнения варианта и площади:

```json
{
  "message": "механизированная, 90 квадратных метров",
  "conversation_id": "chat-example-001",
  "history": [
    {"role": "user", "content": "Нужна штукатурка стен"},
    {"role": "assistant", "content": "Уточните вид и площадь."}
  ]
}
```

Сокращённый пример ответа (идентификаторы генерируются заново):

```json
{
  "answer": "Механизированная штукатурка стен: 90 м² × 750 ₽ = 67 500 ₽.",
  "mode": "llm",
  "calculation_id": "calc-generated-id",
  "selection": {
    "conversation_id": "chat-example-001",
    "revision": 1,
    "items": [{"status": "ready", "service_id": 1, "quantity": "90", "can_add_to_cart": true}]
  },
  "cart_actions": [{
    "action": "add_to_cart",
    "conversation_id": "chat-example-001",
    "calculation_id": "calc-generated-id",
    "service_id": 1,
    "quantity": "90",
    "unit": "м²",
    "unit_price_rub": "750.00",
    "line_total_rub": "67500.00"
  }]
}
```

Фактический ответ также содержит служебные поля позиции и источника; frontend не должен самостоятельно придумывать отсутствующие actions.

## Вызов модели

Используется OpenAI-compatible endpoint `{LLM_BASE_URL}/chat/completions` с Bearer token. Timeout и максимальная длина задаются `LLM_TIMEOUT_SECONDS` и `LLM_MAX_TOKENS`. Для 429/500/502/503/504 выполняются две повторные попытки с задержками 0.25 и 0.75 секунды.

При timeout, rate limit, connection error или некорректном JSON пользователь получает рабочий demo-ответ и предупреждение. Health endpoint раскрывает режим, тип провайдера, признак настройки и model, но не URL и ключ.

## Локальная Qwen3

Compose profile `local` запускает Ollama и одноразовый `ollama-init`. По умолчанию используется `qwen3:1.7b`, context 4096, один загруженный model и один параллельный запрос. Порт 11434 не публикуется. Модель хранится в volume `ollama_models`.

```bash
docker compose --profile local up --build -d
./scripts/check_local_llm.sh
```

## Административный помощник

Он получает агрегаты: counts, total estimate, overdue new orders и среднее время первой обработки. Персональные данные заявок модели не передаются. Ответ не выполняет мутаций.

## Настройка remote

```env
LLM_MODE=remote
LLM_API_KEY=replace-with-secret
LLM_BASE_URL=https://provider.example/v1
LLM_MODEL=model-name
LLM_TIMEOUT_SECONDS=25
LLM_MAX_TOKENS=350
```

Никогда не коммитьте `.env`. Если ключ был опубликован в чате, issue или commit, отзовите его у провайдера и создайте новый.
