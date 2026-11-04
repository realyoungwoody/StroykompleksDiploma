# База данных

Проект использует SQLite через SQLAlchemy. В Docker файл хранится в именованном volume `stroykompleks_data` по пути `/data/stroykompleks.sqlite3`; обычный `docker compose down` его сохраняет.

## Таблицы

| Таблица | Назначение | Важные поля |
| --- | --- | --- |
| `services` | каталог | уникальный `slug`, цена, единица, active, sort order |
| `orders` | заявка | публичный номер, нормализованный телефон, status, total, idempotency |
| `order_items` | зафиксированные позиции | snapshots названия, единицы и цены |
| `order_status_history` | аудит статусов | старый/новый статус, admin id, время |
| `admin_users` | вход администратора | email, Argon2 hash, active |

Статусы заказа ограничены: `new`, `contacted`, `in_progress`, `completed`, `cancelled`. Удаление заказа каскадно удаляет позиции и историю; удаление услуги оставляет позицию заказа, устанавливая `service_id = NULL`.

## Миграции

Alembic настроен в `backend/alembic.ini`. Миграция `0001_initial` создаёт схему из SQLAlchemy metadata. Входной скрипт применяет миграции при каждом старте, поэтому они должны быть обратносуместимыми с текущим кодом и данными.

Новая миграция:

```bash
cd backend
../.venv/bin/alembic revision -m "describe change"
../.venv/bin/alembic upgrade head
```

Проверяйте сгенерированный файл вручную. Для production deployment скрипт создаёт online backup текущей SQLite перед обновлением, если обнаруживает поддерживаемый URL `/data/*.sqlite3`.

## Резервное копирование и восстановление

Production-скрипт сохраняет `shared/backups/<sha>-predeploy.sqlite3` с permission 600. Копируйте backups на отдельный носитель и периодически проверяйте их целостность.

```bash
python3 -c "import sqlite3; db=sqlite3.connect('/opt/stroykompleks/shared/backups/<file>.sqlite3'); print(db.execute('PRAGMA integrity_check').fetchone()[0])"
```

Восстановление — ручная административная операция: остановите Compose-проект, сохраните текущий volume отдельной копией, замените SQLite выбранным проверенным backup, затем запустите совместимый release и выполните healthcheck. Не восстанавливайте старую схему поверх нового кода вслепую и не используйте `down -v`.

## Seed и сброс

Seed добавляет 8 услуг, 12 FAQ в памяти приложения, администратора и 11 демонстрационных заявок. Он не перезаписывает существующие записи. `scripts/reset_demo_data.sh` намеренно удаляет volumes только после ввода `RESET`; это необратимая операция для локальных данных.
