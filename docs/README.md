# Документация «Стройкомплекс»

Этот раздел описывает фактическое состояние учебной демонстрационной системы. Начните с [обзора архитектуры](architecture/overview.md), затем выберите нужный сценарий.

## Содержание

- Архитектура: [общая схема](architecture/overview.md), [frontend](architecture/frontend.md), [backend](architecture/backend.md), [база данных](architecture/database.md), [диаграммы](architecture/diagrams.md).
- Возможности: [каталог](features/catalog.md), [корзина и цены](features/cart-and-pricing.md), [заявки](features/orders.md), [панель администратора](features/admin-panel.md), [ИИ-помощники](features/ai-assistants.md).
- API: [правила работы](api/overview.md) и [справочник endpoints](api/endpoints.md).
- Запуск и эксплуатация: [переменные окружения и `.env`](deployment/environment.md), [локальная разработка](deployment/local-development.md), [Docker](deployment/docker.md), [production](deployment/production.md), [CI/CD](deployment/cicd.md), [устранение неполадок](deployment/troubleshooting.md).
- Качество: [безопасность](security/security-overview.md), [тестирование](testing/testing-guide.md), [вклад в проект](development/contributing.md), [структура репозитория](development/project-structure.md).

## Быстрые маршруты

- Первый запуск: [Docker Compose](deployment/docker.md#первый-запуск).
- Все параметры `.env`: [справочник окружения](deployment/environment.md).
- Разработка без контейнеров: [локальная среда](deployment/local-development.md).
- Настройка внешней или локальной LLM: [ИИ-помощники](features/ai-assistants.md).
- Подготовка сервера: [production-развёртывание](deployment/production.md).
- Ошибка запуска или ИИ: [troubleshooting](deployment/troubleshooting.md).
- Проверка перед Pull Request: [testing guide](testing/testing-guide.md).

## Границы проекта

Это MVP для ВКР, а не официальный сайт, платёжная система или CRM. Заявки и цены демонстрационные. Интеграции с 1С, SMS, почтой, оплатой и реальными сотрудниками отсутствуют. Предварительный расчёт не является офертой.
