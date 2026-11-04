#!/bin/sh
set -eu

compose="docker compose --profile local"
$compose ps ollama ollama-init backend
$compose exec -T ollama ollama show "${LLM_MODEL:-qwen3:1.7b}" >/dev/null
$compose exec -T backend python -c '
import time
import httpx
from app.core.config import get_settings
s = get_settings()
started = time.monotonic()
r = httpx.post(
    s.llm_base_url.rstrip("/") + "/chat/completions",
    headers={"Authorization": "Bearer " + (s.llm_api_key or "ollama")},
    json={"model": s.llm_model, "messages": [{"role": "user", "content": "Ответь одним словом: готов /no_think"}], "max_tokens": 20},
    timeout=s.llm_timeout_seconds,
)
r.raise_for_status()
content = r.json()["choices"][0]["message"]["content"].strip()
assert content
print(f"Local inference: PASS ({time.monotonic() - started:.2f}s)")
'
docker stats --no-stream "$($compose ps -q ollama)"
