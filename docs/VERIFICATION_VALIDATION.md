# Отчёт о верификации и валидации

Дата последней полной автоматизированной проверки: 4 ноября 2026 года. Цель — подтвердить соответствие MVP техническому заданию и пригодность для демонстрации основных клиентских и административных сценариев.

## Среда и методы

- host: macOS; backend-контейнер и CI используют Python 3.12;
- backend: FastAPI 0.115.6, SQLAlchemy 2.0.36, Pydantic 2.10.4;
- frontend: React 18.3.1, TypeScript 5.7.2, Vite 6.4.5, Vitest 5.0.5;
- методы: pytest/TestClient, Ruff, TypeScript, Vitest, production build, локальная браузерная проверка через Vite + Uvicorn;
- Docker Compose build, запуск и HTTP smoke выполнены; backend и web достигли состояния `healthy`.

## Матрица трассируемости

| ID | Требование | Метод | Тест/сценарий | Результат |
|---|---|---|---|---|
| FR-01 | Просмотр каталога | API + UI | API catalog, browser home | PASS |
| FR-02 | Поиск и фильтрация | UI + typecheck | компоненты каталога | PASS |
| FR-03 | Добавление в корзину | UI | браузер: две услуги | PASS |
| FR-04 | Изменение количества | UI | browser 20 м² + 10 м² | PASS |
| FR-05 | Расчёт цены | Unit + API + UI | `test_price_example` | PASS |
| FR-06 | Создание заявки | Integration + UI | `test_create_track_and_idempotency`, browser | PASS |
| FR-07 | Сохранение в БД | Integration | проверка ORM/SQLite | PASS |
| FR-08 | Проверка статуса | Integration + UI | корректный и неверный телефон | PASS |
| FR-09 | Авторизация администратора | Integration + UI | login / wrong password | PASS |
| FR-10 | Изменение статуса | Integration + UI | PATCH + browser | PASS |
| FR-11 | Управление каталогом | Integration | price/active PATCH | PASS |
| FR-12 | Клиентский агент | Functional + UI | 20 м² штукатурки | PASS |
| FR-13 | Админ-агент | Functional/API | агрегированная сводка | PASS |
| FR-14 | Fallback ИИ | Unit + Integration | `LLM_MODE=demo` | PASS |
| FR-15 | Адаптивность | UI | 663 px viewport browser | PASS |
| FR-16 | Docker запуск | Smoke | Compose build, up, health, HTTP smoke | PASS |
| FR-17 | Защита admin API | Security | `test_unauthorized` | PASS |
| FR-18 | Историческая цена | Integration | `test_historical_price` | PASS |
| FR-19 | Идемпотентность | Integration | same/different fingerprint | PASS |
| FR-20 | Данные после пересоздания контейнера | Compose smoke | persistent volume повторно подключён | PASS |

## Результаты команд

- `pytest -q`: **197 passed**, 0 failed; два предупреждения о deprecated startup hook FastAPI.
- `ruff check app tests`: **PASS**, ошибок нет.
- `npm run typecheck`: **PASS**.
- `npm test`: **22 passed**, 0 failed.
- `npm run build`: **PASS**, Vite 6.4.5 production build.
- Docker Compose build/smoke: **PASS**; health сообщил подключённую SQLite и настроенный remote AI provider.
- Полноценный Playwright test suite: **NOT RUN**; вместо него выполнена интерактивная браузерная проверка.

## Практическая валидация

### Задача A — клиент самостоятельно оформляет обращение

Предусловия: локальные Uvicorn/Vite и seed. Шаги: на главной добавлены штукатурка и покраска, количества изменены на 20 и 10, получен расчёт 19 200 ₽, форма заполнена тестовыми данными, заявка создана, затем найдена по номеру и телефону. Фактический результат совпал с ожидаемым. Вывод: сценарий пригоден для демонстрации.

### Задача B — администратор не теряет обращение

Предусловия: созданная заявка и admin cookie. Шаги: вход, поиск новой записи в таблице, открытие карточки, сохранение заметки и статуса «В работе», повторная клиентская проверка. История получила новое событие; клиент увидел «В работе». Вывод: сквозная прозрачность подтверждена.

### Задача C — ИИ сокращает типовые консультации

Запрос: «Сколько стоит 20 м² механизированной штукатурки?». Demo assistant нашёл реальную услугу из БД, вызвал расчёт и вернул 15 000 ₽ с кнопкой добавления. Персональные/admin данные не раскрыты. Вывод: fallback полезен без внешнего ключа.

## Исправленные дефекты

1. API-клиент терял `Content-Type` при добавлении `Idempotency-Key`; браузерная форма получала 422. Исправлен порядок объединения `RequestInit.headers`, добавлено отображение Pydantic validation details.
2. Origin-проверка отклоняла PATCH через Vite dev proxy. Добавлен строгий разбор hostname и локальный allowlist; production same-origin остаётся обязательным.
3. Демонстрационный домен `example.test` отклонялся `email-validator`; placeholder заменён на `example.com`.
4. Типы Python 3.12 не интерпретировались в host Python 3.9; добавлен `eval-type-backport` только для совместимости локальных проверок.
5. Исправлена TSX-скобка в рендере позиций корзины.

## Security и нефункциональные проверки

Подтверждены: Argon2 hash, HttpOnly/SameSite cookie, Origin/CSRF check изменяющих admin операций, закрытые admin endpoints, одинаковая нейтральная ошибка tracking, server-side цены, лимиты размеров, отсутствие `dangerouslySetInnerHTML`, маскирование контактов перед LLM, in-memory rate limit login/track. Реальные секреты не добавлены в Git; `.env` исключён.

Визуально подтверждены mobile navigation, отсутствие горизонтального overflow публичной страницы, рабочие формы, статусы и чат. Ошибок консоли в проверенных сценариях не обнаружено.

## Оценка потенциального эффекта цифровизации

Сценарная формула: `20 × (15 − 5) = 200 минут = 3 часа 20 минут`.

**Сценарный расчёт на условных исходных данных. Не является результатом фактического производственного эксперимента и не подтверждает экономию ООО «Стройкомплекс».** Система отдельно измеряет время до первого изменения статуса, когда наблюдение существует.

## Известные ограничения и вывод

Автоматизированы Docker/Nginx smoke и обе ветки LLM через mocks/fallback; реальный production VPS, DNS, HTTPS, rollback и восстановление backup требуют отдельной инфраструктуры. Keyword retrieval упрощён и не является полноценным семантическим поиском. Rate limit сбрасывается при рестарте.

Итог: функциональные P0-сценарии на уровне кода, API и локального браузера подтверждены; MVP пригоден для демонстрации ВКР. Перед защитой на целевом компьютере следует один раз выполнить Docker smoke из README.
