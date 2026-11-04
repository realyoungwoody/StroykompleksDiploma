# Production-развёртывание

Production workflow рассчитан на один Linux VPS с Docker Compose, SQLite volume и внешним HTTPS reverse proxy. Это демонстрационная схема, а не высокодоступный кластер.

## Требования

- Linux, Docker Engine и Compose plugin;
- `curl`, `tar`, OpenSSH server;
- отдельный непривилегированный deploy user с доступом к Docker;
- DNS и HTTPS termination перед портом `127.0.0.1:8080`;
- каталог, например `/opt/stroykompleks`.

Для Ubuntu установите Docker Engine из официального apt-репозитория по [актуальной инструкции Docker](https://docs.docker.com/engine/install/ubuntu/), включая `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin` и `docker-compose-plugin`. Затем проверьте:

```bash
sudo systemctl enable --now docker
sudo docker run --rm hello-world
docker compose version
```

Создайте отдельного пользователя и структуру каталогов (имена адаптируйте под сервер):

```bash
sudo useradd --create-home --shell /bin/bash deploy
sudo usermod -aG docker deploy
sudo install -d -o deploy -g deploy -m 750 \
  /opt/stroykompleks/releases \
  /opt/stroykompleks/shared/incoming \
  /opt/stroykompleks/shared/backups
```

Группа `docker` фактически даёт root-equivalent доступ; используйте отдельную учётную запись и SSH key. Новая group membership применяется после повторного входа.

## Серверная структура

```text
/opt/stroykompleks/
├── current -> releases/<sha>
├── releases/<sha>/
└── shared/
    ├── .env
    ├── backups/
    ├── incoming/
    └── deployed_sha
```

Создайте `/opt/stroykompleks/shared/.env` с owner deploy и permission 600. Для HTTPS установите `COOKIE_SECURE=true`, сильные ADMIN_PASSWORD/SESSION_SECRET и выбранный LLM mode. Секреты не должны находиться в GitHub Variables или Git. Первый local-LLM deploy может скачивать модель и ждать готовность до 30 минут; volume сохраняется между releases.

## GitHub Environment

Environment `production` использует secrets:

- `DEPLOY_HOST`, `DEPLOY_USER`;
- `DEPLOY_SSH_KEY` — отдельный private key;
- `DEPLOY_KNOWN_HOSTS` — заранее проверенный host key.

Variables: `DEPLOY_PORT`, `DEPLOY_PATH`, `PRODUCTION_URL` (обязательно HTTPS).

## Процесс release

Release выполняется отдельным PR `dev → main`. После merge новый push-CI `main` должен пройти. CD сверяет, что проверенный SHA всё ещё HEAD `main`, создаёт immutable git archive, отправляет его на сервер и вызывает `scripts/deploy_release.sh`.

Скрипт:

1. валидирует пути и SHA;
2. распаковывает новый release и подключает только `shared/.env`;
3. проверяет Compose и собирает images;
4. создаёт SQLite online backup текущего backend;
5. запускает новый release и миграции;
6. проверяет локальные и публичные endpoints;
7. для local mode ждёт готовность модели до 30 минут;
8. только после успеха переключает `current`;
9. хранит пять последних releases.

## Rollback

При ошибке после начала запуска скрипт пытается вернуть предыдущий release и проверяет его health, но deployment всё равно считается failed. Кодовый rollback не выполняет downgrade БД. Перед восстановлением SQLite из `shared/backups` остановите приложение и оцените совместимость схемы.

## Обязательная защита

- HTTPS и `COOKIE_SECURE=true`;
- firewall: наружу только 80/443 и ограниченный SSH;
- запрет публикации 8000 и 11434;
- branch protection и required CI checks;
- регулярное внешнее копирование SQLite и проверка восстановления;
- ротация SSH/LLM/admin secrets;
- мониторинг диска, памяти, health и логов.

SQLite подходит только для одного backend. Для нескольких реплик мигрируйте на серверную СУБД.
