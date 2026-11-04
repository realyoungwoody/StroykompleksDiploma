# Безопасность

Документ описывает реализованные меры и известные границы MVP. Он не заменяет независимый аудит перед обработкой реальных данных.

## Реализовано

- Argon2 password hashing; plaintext password не хранится.
- Подписанная admin-сессия в HttpOnly, SameSite=Lax cookie на 12 часов.
- `COOKIE_SECURE` для production HTTPS.
- Проверка active admin на каждом закрытом endpoint.
- Origin/CSRF-проверка изменяющих admin-операций.
- Rate limit login и public tracking по IP.
- Нейтральная ошибка tracking и требование номера + телефона.
- Серверная валидация и расчёт цен; snapshots в заказе.
- Идемпотентность создания заявки.
- Pydantic limits на длину, количество и форматы.
- SQLite foreign keys, constraints и уникальные индексы.
- LLM не выполняет мутации; actions перепроверяются сервером и клиентом.
- Local Ollama не публикуется наружу; health не раскрывает key/base URL.
- Markdown без raw HTML; `dangerouslySetInnerHTML` не используется.
- `.env` исключён из Git; CI использует изолированные тестовые значения.

## Секреты

Секретами являются `ADMIN_PASSWORD`, `SESSION_SECRET`, `LLM_API_KEY`, deploy SSH key и provider tokens. Храните локальные runtime values в `.env` с ограниченными permissions, production deploy values — в GitHub Secrets и `shared/.env` сервера.

Не помещайте секреты в README, PR body, issue, commit, screenshot или чат. Если значение раскрыто, недостаточно удалить текст: отзовите credential у источника, создайте новый, обновите runtime и проверьте историю/логи.

## Известные ограничения

- Rate limiter хранится в RAM, сбрасывается при restart и не координируется между репликами.
- Нет MFA, password reset, account lockout и ролевой модели.
- Cookie — подписанная, но не server-revocable до истечения, кроме деактивации admin.
- CORS allowlist жёстко содержит только локальные origins; production полагается на same-origin Nginx.
- Нет CSP/HSTS/security headers в приложении; их должен выставлять HTTPS reverse proxy.
- SQLite не шифруется приложением и не подходит для multi-instance.
- Нет malware upload surface, но также нет WAF, централизованного audit log и SIEM.
- Dependency audit может содержать transitive alerts; их нужно оценивать отдельными совместимыми обновлениями.
- Данные пользователя не предназначены для реальной эксплуатации этого demo.

На контрольной проверке 4 ноября 2026 `npm audit` сообщил 3 high findings в цепочке `react-router-dom 7.1.1 → react-router → turbo-stream`; исправление доступно обновлением `react-router-dom` до 7.18.5. Текущий SPA не использует React Router framework/SSR actions, к которым относится часть advisories, но это не отменяет обновление: его следует выполнить отдельным PR с typecheck, UI-тестами и production build.

## Production checklist

- HTTPS, HSTS и `COOKIE_SECURE=true`;
- сильные уникальные secrets и план ротации;
- firewall, непубличные backend/Ollama ports;
- проверенный reverse proxy headers;
- GitHub branch protection и least-privilege deploy user;
- регулярный dependency/CodeQL review;
- backup вне VPS и тест восстановления;
- ограничение логов без payload/секретов;
- отдельный privacy/legal review до реальных персональных данных.
