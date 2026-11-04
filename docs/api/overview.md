# API: общие правила

Base path: `/api/v1`. Интерактивная OpenAPI-документация доступна по `/api/docs`, схема — `/api/openapi.json`.

## Формат

Запросы и ответы используют JSON, денежные Decimal обычно сериализуются строками. Даты — ISO 8601. Frontend отправляет `Content-Type: application/json` и cookie через `credentials: include`.

Явная бизнес-ошибка:

```json
{"error":{"code":404,"message":"Услуга не найдена"}}
```

Ошибка Pydantic использует стандартный массив `detail`. Основные коды: 401 — нет admin-сессии, 403 — неверный Origin, 404 — ресурс/заявка не найдены, 409 — конфликт, 422 — валидация, 429 — rate limit.

## Аутентификация

Public endpoints не требуют входа. Admin API использует HttpOnly cookie `admin_session`, которую устанавливает login. Для изменяющих admin-запросов браузер должен передать same-origin `Origin`.

Пример login:

```bash
curl -i -c cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"your-password"}' \
  http://localhost:8080/api/v1/admin/auth/login
```

## Идемпотентность

При создании заявки рекомендуется уникальный `Idempotency-Key` длиной до 64 символов. Повторяйте тот же ключ только с идентичным JSON. Сервер сравнивает SHA-256 fingerprint канонического payload.

## Versioning

Текущая версия зафиксирована в URL как `v1`. Обратная совместимость публичных контрактов должна сохраняться в пределах ветки; breaking change требует новой версии или контролируемой миграции frontend и backend одновременно.

Полный список приведён в [справочнике endpoints](endpoints.md).
