# CI/CD

## Ветки

- `main` — production и default branch;
- `dev` — интеграционная ветка;
- отдельная ветка задачи → Pull Request в `dev`;
- release — отдельный Pull Request `dev → main`.

Прямые push/force/delete в `main` запрещаются branch protection. `dev` также защищается от force и удаления. Автоматический merge в `main` проектом не выполняется.

## CI

`.github/workflows/ci.yml` запускается для PR и push в `dev`/`main`:

1. `backend-tests`: Python 3.12, Ruff, pytest с отдельной SQLite и `LLM_MODE=demo`.
2. `frontend-tests`: Node 22, `npm ci`, typecheck, Vitest, production build.
3. `docker-build`: изолированный `.env`, Compose config, shell syntax, images, containers и smoke test.

Workflow имеет `contents: read`, не использует production secrets и всегда удаляет одноразовые CI volumes. Concurrency отменяет устаревший run той же ветки/PR.

CodeQL включён через GitHub default setup и отдельными проверками анализирует Python и JavaScript/TypeScript; workflow-файла CodeQL в репозитории нет.

## CD

`.github/workflows/deploy.yml` слушает завершённый `CI` только для `main`. Deploy разрешён, если:

- conclusion — success;
- событие CI — push, не PR;
- branch — main и repository совпадает;
- проверенный SHA всё ещё HEAD main.

Deploy jobs сериализованы. Checkout, archive и release используют один verified SHA. После SSH выполняются локальный healthcheck, возможный rollback и независимая проверка публичного HTTPS.

## Required checks

Для PR в `main` обязательны `backend-tests`, `frontend-tests`, `docker-build`, актуальная ветка и resolution conversations. Аналогичные checks рекомендуются для PR в `dev`. После изменения имени job обновите ruleset, иначе merge может быть заблокирован или защита ослаблена.

## Работа с зависимостями

Dependabot PR должен быть направлен в `dev`, обновлён относительно актуальной базы и пройти все checks. Major update нельзя сливать только по зелёному старому run: проверьте peer dependencies, lock-файл, typecheck и Docker build.

Исторический документ [`docs/CI_CD.md`](../CI_CD.md) сохранён как ссылка на эту актуальную страницу.
