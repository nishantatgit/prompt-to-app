#!/usr/bin/env bash
# What is prod serving? Checks the frontend bundle and the backend API.
set -uo pipefail
for host in app.vyskar.com vyskar.com; do
  echo "== https://$host"
  HTML=$(curl -sS -m 20 "https://$host/")
  JS=$(echo "$HTML" | grep -o 'src="/assets/[^"]*\.js"' | head -1 | cut -d'"' -f2)
  echo "bundle: $JS"
  [ -z "$JS" ] && continue
  B=$(curl -sS -m 20 "https://$host$JS")
  for s in "Build steps" "builder_mode" "Your API key did not work" "Cancel build"; do
    printf "  %-28s %s\n" "$s" "$(echo "$B" | grep -c "$s")"
  done
  echo "  api urls: $(echo "$B" | grep -oE 'https://[a-z0-9.-]+(fly\.dev|vyskar\.com)[^"]*' | sort -u | tr '\n' ' ')"
done
for api in https://backend-satin-skylark-1693.fly.dev https://api.vyskar.com; do
  echo "== $api"
  curl -sS -m 20 "$api/api/health"; echo
  curl -sS -m 20 "$api/api/jobs/does-not-exist"; echo
  curl -sS -m 30 -X POST "$api/api/build" -H 'Content-Type: application/json' -d '{"prompt":"x","provider":"anthropic","api_key":"sk-ant-invalid"}'; echo
done
