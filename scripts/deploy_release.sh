#!/usr/bin/env bash
set -Eeuo pipefail

deploy_root=${1:?deployment root is required}
release_sha=${2:?release SHA is required}
production_url=${3:-}
compose_project=stroykompleks
keep_releases=5

if [[ ! "$deploy_root" =~ ^/[A-Za-z0-9._/-]+$ ]] || [[ "$deploy_root" == "/" ]]; then
  echo "Unsafe deployment root" >&2
  exit 2
fi
if [[ ! "$release_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Invalid release SHA" >&2
  exit 2
fi

releases_dir="$deploy_root/releases"
shared_dir="$deploy_root/shared"
release_dir="$releases_dir/$release_sha"
archive="$shared_dir/incoming/$release_sha.tar.gz"
current_link="$deploy_root/current"
previous_release=""
deployment_started=0

if [[ -L "$current_link" ]]; then
  previous_release=$(readlink -f "$current_link")
fi

compose_for() {
  local directory=$1
  docker compose -p "$compose_project" --env-file "$shared_dir/.env" -f "$directory/docker-compose.yml" "${@:2}"
}

healthcheck() {
  local attempts=${1:-20}
  local base_url=http://127.0.0.1:8080
  local attempt
  for ((attempt=1; attempt<=attempts; attempt++)); do
    if curl -fsS --max-time 5 "$base_url/api/v1/health" >/dev/null \
      && curl -fsS --max-time 5 "$base_url/" >/dev/null; then
      return 0
    fi
    sleep 3
  done
  return 1
}

rollback() {
  if [[ -n "$previous_release" && -f "$previous_release/docker-compose.yml" ]]; then
    echo "Restoring previous release: $(basename "$previous_release")" >&2
    compose_for "$previous_release" up -d --build
    ln -sfn "$previous_release" "$deploy_root/.current-rollback"
    mv -Tf "$deploy_root/.current-rollback" "$current_link"
    if healthcheck 20; then
      echo "Previous release restored; deployment still fails by design." >&2
    else
      echo "Rollback healthcheck failed." >&2
    fi
  else
    echo "No previous release is available for rollback." >&2
  fi
}

on_error() {
  local exit_code=$?
  trap - ERR
  if [[ "$deployment_started" -eq 1 ]]; then
    compose_for "$release_dir" ps >&2 || true
    compose_for "$release_dir" logs --no-color --tail=200 >&2 || true
    rollback || true
  fi
  exit "$exit_code"
}
trap on_error ERR

test -f "$archive"
test -f "$shared_dir/.env"
mkdir -p "$releases_dir" "$shared_dir/backups"

if [[ -d "$release_dir" ]]; then
  rm -rf -- "$release_dir"
fi
mkdir -p "$release_dir"
tar -xzf "$archive" -C "$release_dir"
ln -s "$shared_dir/.env" "$release_dir/.env"

compose_for "$release_dir" config --quiet
compose_for "$release_dir" build

current_backend=$(compose_for "$release_dir" ps -q backend 2>/dev/null || true)
if [[ -n "$current_backend" ]] && docker inspect "$current_backend" >/dev/null 2>&1; then
  database_url=$(grep -E '^DATABASE_URL=' "$shared_dir/.env" | tail -n 1 | cut -d= -f2-)
  if [[ "$database_url" =~ ^sqlite:////data/([A-Za-z0-9._-]+)$ ]]; then
    database_file=${BASH_REMATCH[1]}
    backup_file="$shared_dir/backups/${release_sha}-predeploy.sqlite3"
    docker exec "$current_backend" python -c \
      "import sqlite3; source=sqlite3.connect('/data/$database_file'); target=sqlite3.connect('/tmp/predeploy.sqlite3'); source.backup(target); target.close(); source.close()"
    docker cp "$current_backend:/tmp/predeploy.sqlite3" "$backup_file"
    docker exec "$current_backend" rm -f /tmp/predeploy.sqlite3
    chmod 600 "$backup_file"
    echo "SQLite backup created for release $release_sha"
  else
    echo "DATABASE_URL is not a supported /data SQLite URL; refusing deployment." >&2
    exit 1
  fi
fi

deployment_started=1
compose_for "$release_dir" up -d --remove-orphans
healthcheck 30
compose_for "$release_dir" ps
if [[ -n "$production_url" ]]; then
  curl -fsS --location --retry 10 --retry-delay 3 --retry-all-errors --max-time 10 \
    "${production_url%/}/api/v1/health" >/dev/null
  curl -fsS --location --retry 5 --retry-delay 2 --retry-all-errors --max-time 10 \
    "${production_url%/}/" >/dev/null
fi

ln -sfn "$release_dir" "$deploy_root/.current-next"
mv -Tf "$deploy_root/.current-next" "$current_link"
printf '%s\n' "$release_sha" > "$shared_dir/deployed_sha"
chmod 600 "$shared_dir/deployed_sha"
rm -f -- "$archive"

mapfile -t release_paths < <(find "$releases_dir" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -rn | cut -d' ' -f2-)
for ((index=keep_releases; index<${#release_paths[@]}; index++)); do
  old_release=${release_paths[$index]}
  old_name=$(basename "$old_release")
  if [[ "$old_release" == "$releases_dir/"* ]] && [[ "$old_name" =~ ^[0-9a-f]{40}$ ]] && [[ "$old_release" != "$release_dir" ]] && [[ "$old_release" != "$previous_release" ]]; then
    rm -rf -- "$old_release"
  fi
done

echo "Deployment completed for $release_sha"
if [[ -n "$production_url" ]]; then
  echo "Public verification requested for ${production_url%%\?*}"
fi
