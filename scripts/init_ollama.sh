#!/bin/sh
set -eu

model=${OLLAMA_MODEL:?OLLAMA_MODEL is required}
max_attempts=3
attempt=1

echo "Checking local model: $model"
if ollama show "$model" >/dev/null 2>&1; then
  echo "Model already exists in persistent volume: $model"
else
  while ! ollama pull "$model"; do
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "Model download failed after $max_attempts attempts: $model" >&2
      exit 1
    fi
    attempt=$((attempt + 1))
    echo "Retrying model download ($attempt/$max_attempts): $model" >&2
    sleep 10
  done
fi

echo "Running local inference readiness check: $model"
result=$(ollama run "$model" "Ответь только словом: готов /no_think")
if [ -z "$result" ]; then
  echo "Inference readiness check returned an empty response" >&2
  exit 1
fi
echo "Local model is ready: $model"
