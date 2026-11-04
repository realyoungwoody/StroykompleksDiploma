# Вклад в проект

## Git workflow

1. Обновите `dev` из origin.
2. Создайте отдельную ветку задачи. Для функций используется `feat/<name>`, для документации — `docs/<name>`, для исправлений допустим `fix/<name>`.
3. Внесите атомарные изменения без секретов и generated artifacts.
4. Запустите релевантные проверки и полный набор перед публикацией.
5. Создайте Conventional Commit, например `feat(ai): ...`, `fix(api): ...`, `docs: ...`.
6. Push ветку и откройте PR в `dev`.
7. В PR укажите цель, функции, компоненты, тесты, ограничения и ручную проверку.
8. Дождитесь CI и устраните замечания. Не выполняйте автоматический merge в `main`.

Если PR этой ветки существует, обновляйте его, а не создавайте дубликат. Release в `main` — отдельная задача и PR `dev → main`.

## Стиль изменений

- Backend: type hints, Pydantic validation, SQLAlchemy 2 queries, Ruff.
- Frontend: strict TypeScript, server-authoritative prices, доступные состояния loading/error/success.
- API: сохраняйте нейтральные security errors и совместимость v1.
- AI: LLM отвечает за язык, deterministic code — за выбор, цену и actions.
- DB: schema change сопровождается Alembic migration и тестом.
- Dependencies: package.json и package-lock.json меняются вместе; не используйте force resolution без причины.

## Definition of done

- сценарий реализован и проверен;
- Ruff/pytest/typecheck/Vitest/build проходят;
- Compose config/build/smoke проходят для инфраструктурного изменения;
- документация и `.env.example` обновлены при изменении конфигурации;
- секретов и лишних файлов нет;
- PR создан в `dev`, checks зелёные, URL подтверждён.

## Работа с dirty worktree

Не перезаписывайте чужие изменения. Перед переключением веток проверьте `git status`. Не применяйте `git reset --hard` или удаление широких каталогов. Generated dependencies (`node_modules`, virtualenv, dist) не коммитятся.
