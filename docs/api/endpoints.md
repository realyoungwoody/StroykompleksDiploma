# API endpoints

Все пути ниже начинаются с `/api/v1`.

## Public

| Метод и путь | Назначение | Вход | Результат |
| --- | --- | --- | --- |
| `GET /health` | health/readiness и безопасная AI-диагностика | — | status, database, ai mode/provider/configured/model |
| `GET /services` | активные услуги | — | `Service[]` |
| `GET /services/{slug}` | активная услуга | slug | `Service` или 404 |
| `GET /faq` | FAQ | — | question/answer[] |
| `POST /quotes` | предварительный расчёт | `items[service_id, quantity]` | строки, total, RUB, warning |
| `POST /orders` | заявка | контакты, consent=true, items | номер, status, total, created_at |
| `POST /orders/track` | публичный статус | public_number, phone | status, total, timestamps, snapshots |
| `POST /assistant/chat` | клиентский помощник | message и контекст | answer, mode, selection, actions, warning |

Пример расчёта:

```bash
curl -sS -H 'Content-Type: application/json' \
  -d '{"items":[{"service_id":1,"quantity":"20"}]}' \
  http://localhost:8080/api/v1/quotes
```

Пример заявки:

```bash
curl -sS -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: demo-request-001' \
  -d '{
    "customer_name":"Тестовый клиент",
    "phone":"+7 000 000-00-01",
    "email":null,
    "object_location":"Нижний Новгород",
    "desired_date":null,
    "comment":"Тестовая заявка",
    "consent_accepted":true,
    "items":[{"service_id":1,"quantity":"20"}]
  }' http://localhost:8080/api/v1/orders
```

## Admin auth

| Метод и путь | Назначение |
| --- | --- |
| `POST /admin/auth/login` | проверить Argon2 password, установить cookie |
| `POST /admin/auth/logout` | проверить origin, удалить cookie |
| `GET /admin/auth/me` | текущий admin id/email |

Login ограничен 10 попытками за 300 секунд на IP.

## Admin orders

| Метод и путь | Назначение | Параметры/тело |
| --- | --- | --- |
| `GET /admin/orders` | список | `page`, `page_size` 1–100, `status_filter`, `search`, `sort=asc|desc` |
| `GET /admin/orders/{order_id}` | полная карточка | id |
| `PATCH /admin/orders/{order_id}` | статус/заметка | `{ "status"?, "admin_note"? }` |
| `GET /admin/metrics` | агрегаты | — |

`search` ищет по номеру, имени и нормализованному телефону. PATCH записывает историю статуса; для изменения требуется валидный Origin.

## Admin services

| Метод и путь | Назначение |
| --- | --- |
| `GET /admin/services` | все услуги, включая inactive |
| `POST /admin/services` | создать услугу |
| `PATCH /admin/services/{service_id}` | частично изменить услугу |

Обязательные поля создания: `slug`, `name`, `category`, `short_description`, `description`, `stages`, `base_price_rub`; unit, active и sort order имеют defaults. Цена должна быть больше нуля.

## Admin assistant

`POST /admin/assistant/chat` принимает тот же базовый `ChatIn`, но использует `message` и возвращает агрегированную read-only сводку. Требуется admin cookie; персональные поля заказов не отправляются модели.

## Chat contract

Минимальный запрос:

```json
{"message":"Нужна покраска стен 80 м²","conversation_id":"chat-example-001"}
```

Полный контракт может содержать последние 6 сообщений, до 20 context actions, до 20 cart items и selection. `conversation_id`, `calculation_id` и `selection_item_id` ограничены безопасным набором `[A-Za-z0-9_-]`. Клиент должен считать действия действительными только для текущих conversation/calculation ids.
