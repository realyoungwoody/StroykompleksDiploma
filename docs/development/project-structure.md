# Структура проекта

```text
.
├── backend/
│   ├── alembic/                 # миграции
│   ├── app/
│   │   ├── core/                # config, DB, security
│   │   ├── services/            # pricing, selection, assistants
│   │   ├── main.py              # FastAPI endpoints
│   │   ├── models.py            # SQLAlchemy
│   │   ├── schemas.py           # Pydantic contracts
│   │   └── seed.py              # demo catalog/FAQ/orders/admin
│   ├── tests/                   # pytest
│   ├── Dockerfile
│   └── entrypoint.sh            # migrations + Uvicorn
├── frontend/
│   ├── src/
│   │   ├── api/                 # fetch client
│   │   ├── components/          # layout, chat, UI, cards
│   │   ├── contexts/            # cart and toast
│   │   ├── pages/               # public and admin routes
│   │   ├── types/               # shared frontend types
│   │   ├── App.tsx
│   │   └── styles.css
│   ├── tests/                   # Vitest/Testing Library
│   ├── Dockerfile
│   └── nginx.conf
├── scripts/                     # smoke, reset, Ollama, deploy
├── docs/                        # тематическая документация
├── .github/workflows/           # CI, CodeQL, deploy
├── docker-compose.yml
└── .env.example
```

## Где менять поведение

| Задача | Основные файлы |
| --- | --- |
| endpoint/валидация | `backend/app/main.py`, `schemas.py`, tests |
| таблица/поле | `models.py`, Alembic migration, schemas/tests |
| цена | `services/pricing.py` |
| распознавание услуг | `services/selection.py`, `assistant.py` |
| кнопки ИИ | assistant response + `AssistantChat.tsx` |
| корзина | `CartContext.tsx`, `PublicPages.tsx` |
| admin UI | `pages/admin/AdminPages.tsx` |
| окружение | `core/config.py`, `.env.example`, Compose/docs |
| CI/CD | workflows и `scripts/deploy_release.sh` |

Backend и frontend намеренно находятся в одном репозитории: API-контракт и UI изменяются одним PR и проверяются общей CI.
