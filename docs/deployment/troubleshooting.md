# Устранение неполадок

## Сайт не открывается

```bash
docker compose ps
docker compose logs --tail=200 backend web
curl -fsS http://localhost:8080/api/v1/health
```

Если backend unhealthy, проверьте `.env`, `DATABASE_URL`, миграции и permission volume. Если backend healthy, но SPA недоступна, проверьте web logs и занятость порта 8080.

## `npm ci` или Docker build падает

Используйте lock-файл из Git и не копируйте host `node_modules` в образ. Локально удалите/переместите `frontend/node_modules`, выполните `npm ci` и повторите build. Ошибка esbuild `Host version ... does not match binary version` означает смешение бинарников разных платформ.

При dependency conflict сверяйте peer ranges; не применяйте `--force`/`--legacy-peer-deps` как постоянное решение. После изменения package.json пересоздайте и закоммитьте package-lock.json.

## ИИ показывает demo fallback

```bash
curl -sS http://localhost:8080/api/v1/health
docker compose logs --tail=200 backend
```

Проверьте `ai_mode`, `ai_provider`, `ai_configured`, model, timeout и URL. Для remote проверьте действительность key и лимиты провайдера. HTTP 429 означает rate limit/quota; backend повторяет временную ошибку, затем безопасно возвращает demo.

Для local:

```bash
docker compose --profile local ps
docker compose --profile local logs --tail=200 ollama ollama-init backend
./scripts/check_local_llm.sh
docker stats --no-stream
```

Не удаляйте `ollama_models` при прерванной загрузке: повторите `docker compose --profile local up ollama-init`. При нехватке RAM оставьте `qwen3:1.7b` и уменьшите context.

## Ответ ИИ есть, кнопки нет

Кнопка зависит не от фразы LLM, а от structured selection. Уточните вариант услуги и площадь. В DevTools проверьте ответ `/assistant/chat`: selection item должен быть `ready`, `can_add_to_cart=true`, а `cart_actions` — относиться к текущим conversation/calculation ids. После изменения каталога выполните новый расчёт.

## Нельзя войти в admin

- credentials берутся из `.env` только при создании первого admin; изменение env не переписывает существующий hash;
- проверьте cookie и одинаковый host (`localhost` или `127.0.0.1`);
- production через HTTPS требует `COOKIE_SECURE=true`, HTTP localhost — false;
- после 10 ошибок подождите окно rate limit или перезапустите demo backend.

## Заявка не находится

Нужны точный `SC-...` и тот же телефон. Российские номера нормализуются к `+7XXXXXXXXXX`. Нейтральный 404 намеренно не раскрывает, номер или телефон неверен.

## CI не стартовал после смены base PR

GitHub иногда не создаёт новый `pull_request` run только от retarget. Обновите commit ветки или технически закройте и переоткройте тот же PR; не создавайте дубликат. Убедитесь, что base — `dev` или `main`, указанные в workflow.

## Production deploy failed

Проверьте шаг, на котором остановился workflow. Ошибка до SSH не меняет сервер. Build error сохраняет текущий release. Ошибка после освобождения порта или старта вызывает diagnostics и попытку rollback. Сверьте `shared/deployed_sha`, `current`, backups, container logs и public HTTPS; не выполняйте `down -v`.

Ошибка `Bind for 0.0.0.0:8080 failed: port is already allocated` означает, что порт удерживает другой контейнер. Актуальный deploy-скрипт безопасно останавливает старый `web`, если по Compose labels, deployment path или имени legacy image подтверждается принадлежность этому проекту. Для неизвестного контейнера он выводит его id, project, service и image и отказывается завершать чужой workload. В таком случае найдите владельца командой `docker ps --filter publish=8080` и исправьте конфликт вручную, не удаляя volumes.
