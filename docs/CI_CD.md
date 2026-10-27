# CI/CD проекта «Стройкомплекс»

## Назначение

GitHub Actions проверяет каждый кандидат на слияние в `dev` и `main`, повторно проверяет фактические push в эти ветки и допускает production deployment только после успешного CI для актуального commit ветки `main`. CI не получает production secrets. CD никогда не запускается из pull request или `dev`.

## Стратегия ветвления

- `main` — защищённая production-ветка и default branch;
- `dev` — интеграционная ветка текущей разработки;
- `feat/*` — ветки отдельных задач, открывающие PR в `dev`;
- релиз оформляется отдельным PR `dev → main`.

Обычный цикл: `feat/*` → PR в `dev` → CI → merge → PR `dev` в `main` → CI → merge → CI push в `main` → CD.

Прямой push в `main`, force push и удаление `main` должны быть запрещены. Прямой push в `dev` разрешён, но его CI выполняется уже после записи коммита и не может отменить неуспешный push.

## CI

Workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) называется `CI` и запускается:

- для pull request в `dev` или `main`;
- для push в `dev` или `main`.

Устаревший запуск той же ветки или того же PR отменяется через `concurrency`; разные PR используют разные группы. Path filters отсутствуют, поэтому required checks появляются для каждого PR.

Jobs имеют стабильные имена:

1. `backend-tests`: Python 3.12, установка `backend/requirements.txt`, Ruff и pytest. Тесты принудительно используют отдельную SQLite и `LLM_MODE=demo`.
2. `frontend-tests`: Node.js 22, npm cache, `npm ci`, TypeScript typecheck, Vitest и production build.
3. `docker-build`: тестовый `.env`, `docker compose config`, сборка обоих образов, запуск контейнеров и HTTP smoke checks. После проверки временный volume удаляется только на одноразовом CI runner.

Workflow имеет только `contents: read`, не использует `pull_request_target`, production secrets, `continue-on-error` или маскирование ошибок.

## CD и проверенный SHA

Workflow [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) называется `Deploy Production` и слушает завершение `CI` через `workflow_run`. Job развёртывания выполняется только если одновременно истинны условия:

- CI завершился с `success`;
- исходным событием CI был `push`, а не pull request;
- `head_branch` равен `main`;
- исходный репозиторий совпадает с текущим;
- `workflow_run.head_sha` всё ещё равен HEAD `main`, полученному через GitHub API.

Checkout и архив создаются именно из `workflow_run.head_sha`. Более старый успешный workflow безопасно остановится до SSH, если в `main` уже появился новый commit. Деплои сериализованы группой `production-deploy` и не отменяют уже начавшийся деплой.

## GitHub Environment, Secrets и Variables

Создайте Environment `production`. Если Environment недоступен на тарифе, задайте те же значения как repository secrets/variables и сохраните branch protection как основной барьер.

Secrets:

| Имя | Назначение |
| --- | --- |
| `DEPLOY_HOST` | DNS-имя или IP VPS |
| `DEPLOY_USER` | отдельный непривилегированный пользователь деплоя |
| `DEPLOY_SSH_KEY` | приватная часть отдельного deployment key |
| `DEPLOY_KNOWN_HOSTS` | заранее проверенная строка host key сервера |

Variables:

| Имя | Пример | Назначение |
| --- | --- | --- |
| `DEPLOY_PORT` | `22` | SSH-порт |
| `DEPLOY_PATH` | `/opt/stroykompleks` | корень releases/shared/current |
| `PRODUCTION_URL` | `https://example.org` | публичный HTTPS URL без секретов |

Ни `.env`, ни приватный ключ не копируются из Git. Значения secrets не должны присутствовать в логах или workflow-файлах.

## Branch Protection / Rulesets

### `main`

В GitHub откройте **Settings → Rules → Rulesets → New branch ruleset** и настройте:

1. Name: `Protect main`, Enforcement status: `Active`.
2. Target branches: include default branch или pattern `main`.
3. Включите **Restrict deletions** и **Block force pushes**.
4. Включите **Require a pull request before merging**.
5. Required approvals: `0`, если разработчик один; не включайте обязательный внешний review.
6. Включите **Require conversation resolution before merging**.
7. Включите **Require status checks to pass** и после первого запуска CI выберите:
   - `backend-tests`;
   - `frontend-tests`;
   - `docker-build`.
8. Включите требование актуальной ветки перед merge, если в интерфейсе оно доступно.
9. Не добавляйте bypass для GitHub Actions или Codex. Не включайте **Lock branch**.
10. Сохраните ruleset и проверьте через тестовый PR, что direct push, force push и deletion заблокированы.

### `dev`

Создайте отдельный ruleset `Protect dev`: target `dev`, block force pushes и deletion. Разрешите direct push. Для PR желательно потребовать те же три checks и resolution conversations, не включая правило, запрещающее все прямые обновления.

Rules считаются применёнными только после сохранения и фактической проверки в GitHub. Наличие этой инструкции само по себе не означает, что ветки защищены.

## Первичная подготовка VPS

Нужен Linux VPS с Docker Engine, Compose plugin, `curl`, `tar`, OpenSSH server и публичным HTTPS reverse proxy. Пример выполняется администратором сервера, а не GitHub Actions:

```bash
sudo useradd --create-home --shell /bin/bash deploy
sudo install -d -o deploy -g deploy -m 0750 /opt/stroykompleks
sudo install -d -o deploy -g deploy -m 0750 /opt/stroykompleks/{releases,shared,shared/incoming,shared/backups}
```

Пользователь `deploy` не должен входить по SSH как root. Дайте ему только необходимые права для Docker. Членство в группе `docker` фактически даёт root-equivalent доступ; на production предпочтительнее ограниченный sudo/policy или rootless Docker.

### Deployment key

На доверенной машине:

```bash
ssh-keygen -t ed25519 -a 100 -C stroykompleks-github-deploy -f ./stroykompleks_deploy
```

Публичный ключ добавьте в `/home/deploy/.ssh/authorized_keys`, приватный — в `DEPLOY_SSH_KEY`. Этот ключ не нужен репозиторию как Deploy key, потому что сервер не выполняет `git pull`.

Host key получите по защищённому административному каналу непосредственно на сервере:

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

С другой доверенной сети выполните `ssh-keyscan -t ed25519 HOST`, затем вручную сравните fingerprint с сервером. Только после совпадения сохраните строку `ssh-keyscan` в `DEPLOY_KNOWN_HOSTS`. Workflow не использует `StrictHostKeyChecking=no`.

### Production `.env`

Создайте `/opt/stroykompleks/shared/.env` прямо на VPS с правами `0600`:

```env
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<strong-random-password>
SESSION_SECRET=<at-least-32-random-bytes>
DATABASE_URL=sqlite:////data/stroykompleks.sqlite3
COOKIE_SECURE=true
LLM_MODE=demo
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=25
```

Для автоматической резервной копии текущая реализация ожидает SQLite URL вида `sqlite:////data/<safe-filename>`. База хранится в named volume `stroykompleks_stroykompleks_data`, а не внутри release-каталога.

Публичный reverse proxy должен завершать TLS и проксировать на `127.0.0.1:8080`. Не публикуйте `/data`, внутренний backend-порт или SQLite. До настройки HTTPS, firewall и `COOKIE_SECURE=true` приложение нельзя считать готовым к работе с пользовательскими данными.

## Первая и последующие публикации

1. Подготовьте VPS, `.env`, DNS и HTTPS.
2. Создайте Environment, secrets и variables.
3. Примените branch rulesets.
4. Откройте и объедините PR `dev → main` после трёх успешных checks.
5. Push merge-коммита в `main` запустит новый CI.
6. Только успешный push-CI запустит `Deploy Production`.

Workflow формирует `git archive` проверенного SHA и передаёт его на VPS. Скрипт [`scripts/deploy_release.sh`](../scripts/deploy_release.sh):

- распаковывает `/opt/stroykompleks/releases/<sha>`;
- подключает только серверный `shared/.env`;
- использует постоянное Compose project name `stroykompleks`;
- проверяет Compose config и собирает образы;
- при наличии текущего backend создаёт SQLite online backup в `shared/backups`;
- запускает контейнеры; `backend/entrypoint.sh` применяет Alembic migrations;
- повторяет локальные backend/frontend healthchecks;
- переключает `current` только после успеха и пишет `shared/deployed_sha`;
- хранит последние пять releases, не удаляя активный и предыдущий.

GitHub runner после SSH отдельно проверяет `PRODUCTION_URL` по HTTPS.

## Проверка и эксплуатация

Текущий SHA:

```bash
cat /opt/stroykompleks/shared/deployed_sha
readlink -f /opt/stroykompleks/current
```

Статус и health:

```bash
cd /opt/stroykompleks/current
docker compose -p stroykompleks --env-file /opt/stroykompleks/shared/.env ps
curl -fsS http://127.0.0.1:8080/api/v1/health
curl -fsS https://example.org/api/v1/health
```

Логи:

```bash
cd /opt/stroykompleks/current
docker compose -p stroykompleks --env-file /opt/stroykompleks/shared/.env logs --tail=200
```

Не используйте `docker compose down -v`: ключ `-v` удалит постоянный volume SQLite.

## Rollback

При неуспешном healthcheck скрипт автоматически пытается запустить предыдущий release и повторяет healthcheck, но workflow всё равно завершается ошибкой. Диагностика новых контейнеров выводится в лог.

Ручной rollback к известному SHA:

```bash
ROOT=/opt/stroykompleks
PREVIOUS_SHA=<verified-40-character-sha>
cd "$ROOT/releases/$PREVIOUS_SHA"
docker compose -p stroykompleks --env-file "$ROOT/shared/.env" config --quiet
docker compose -p stroykompleks --env-file "$ROOT/shared/.env" up -d --build
ln -sfn "$ROOT/releases/$PREVIOUS_SHA" "$ROOT/.current-rollback"
mv -Tf "$ROOT/.current-rollback" "$ROOT/current"
curl -fsS http://127.0.0.1:8080/api/v1/health
```

Rollback кода не откатывает миграции. Перед каждым обновлением создаётся SQLite backup, однако destructive downgrade автоматически не выполняется. Восстановление БД из `shared/backups` — отдельная административная операция после остановки приложения и оценки совместимости схемы.

## Диагностика ошибок

### CI

- `backend-tests`: воспроизведите команды из README из каталога `backend`.
- `frontend-tests`: обязательно используйте `npm ci`; при изменении зависимостей обновите и закоммитьте `package-lock.json` через npm.
- `docker-build`: посмотрите шаг `Container diagnostics`, затем локально выполните `docker compose config`, `build`, `up -d` и `scripts/smoke_test.sh` с тестовым `.env`.

### CD

- ошибка SSH до запуска скрипта не изменяет production;
- несовпадение SHA означает, что появился более новый `main`: старый деплой намеренно пропущен;
- отсутствие `shared/.env` останавливает деплой до обновления контейнеров;
- ошибка build оставляет текущие контейнеры без изменений;
- ошибка запуска или healthcheck вызывает диагностику и rollback;
- ошибка внешнего HTTPS после успешного локального healthcheck оставляет новый release активным и требует проверки DNS/reverse proxy. Workflow завершается ошибкой.

## Ограничения и ручные проверки

- Branch rulesets требуют административных прав и должны быть проверены в GitHub.
- Реальный deploy нельзя проверить без VPS, DNS, HTTPS и настроенных secrets/variables.
- Автоматический rollback кода не гарантирует совместимость со схемой после необратимой миграции.
- SQLite подходит для дипломного MVP с одним экземпляром backend, но требует регулярного внешнего резервного копирования.
- Первый deploy не создаёт backup, потому что ещё нет работающего контейнера; volume при этом создаётся один раз под стабильным именем.
- `production` Environment рекомендуется защитить доступными средствами тарифа; обязательное ручное approval не требуется для полностью автоматического CD.
