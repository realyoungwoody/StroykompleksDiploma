#!/bin/sh
set -eu
echo "ВНИМАНИЕ: команда удалит все локальные заявки, услуги и изменения в Docker volume."
printf "Введите RESET для продолжения: "
read answer
[ "$answer" = "RESET" ] || { echo "Отменено"; exit 1; }
docker compose down -v
docker compose up --build -d

