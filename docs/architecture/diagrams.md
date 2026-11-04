# Диаграммы

## Компоненты

```mermaid
flowchart LR
  B[Browser] -->|HTTP :8080| N[Nginx]
  N -->|static SPA| R[React]
  N -->|/api/*| F[FastAPI]
  F --> S[SQLAlchemy]
  S --> D[(SQLite volume)]
  F -->|optional OpenAI-compatible API| L[Remote LLM or Ollama]
  F -->|on failure| X[Deterministic demo fallback]
```

## Жизненный цикл заявки

```mermaid
flowchart LR
  C[Создание заявки] --> N[new]
  N --> P{PATCH администратора}
  CT[contacted] --> P
  IP[in_progress] --> P
  CO[completed] --> P
  CA[cancelled] --> P
  P --> N
  P --> CT
  P --> IP
  P --> CO
  P --> CA
```

Backend хранит историю каждого фактического изменения, но текущий API разрешает администратору выбрать любое значение enum независимо от предыдущего статуса.

## Клиентский ИИ

```mermaid
sequenceDiagram
  participant U as Пользователь
  participant W as React
  participant A as FastAPI
  participant DB as Каталог/цены
  participant L as LLM
  U->>W: сообщение
  W->>A: message + history + cart + selection
  A->>DB: восстановить selection и проверить услуги
  A->>DB: рассчитать готовые позиции
  opt LLM настроена
    A->>L: безопасный контекст и инструкция
    L-->>A: формулировка ответа
  end
  A-->>W: answer + selection + versioned cart_actions
  U->>W: нажать «Добавить»
  W->>A: повторно запросить services и quote
  A-->>W: актуальные данные
  W->>W: изменить локальную корзину
```

## ER-модель

```mermaid
erDiagram
  SERVICES ||--o{ ORDER_ITEMS : referenced_by
  ORDERS ||--|{ ORDER_ITEMS : contains
  ORDERS ||--|{ ORDER_STATUS_HISTORY : records
  ADMIN_USERS ||--o{ ORDER_STATUS_HISTORY : changes
  SERVICES { int id PK string slug decimal base_price_rub boolean is_active }
  ORDERS { int id PK string public_number string phone_normalized string status decimal estimated_total_rub }
  ORDER_ITEMS { int id PK int order_id FK int service_id FK decimal unit_price_snapshot decimal line_total_rub }
  ORDER_STATUS_HISTORY { int id PK int order_id FK int changed_by_admin_id FK string old_status string new_status }
  ADMIN_USERS { int id PK string email string password_hash boolean is_active }
```

## CI/CD

```mermaid
flowchart LR
  F[Task branch] --> P[PR to dev]
  P --> C[CI + CodeQL]
  C -->|success + review| D[dev]
  D --> R[Release PR to main]
  R --> C2[CI]
  C2 --> M[main]
  M --> C3[push CI]
  C3 -->|verified SHA| CD[Production deploy]
  CD --> H[local + public healthchecks]
  H -->|failure| RB[rollback previous release]
```
