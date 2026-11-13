#!/usr/bin/env bash
# Start one small build on prod and watch its mode, stage and loop steps.
set -uo pipefail
API=https://api.vyskar.com
BODY=$(jq -n --arg k "$ANTHROPIC_API_KEY" '{prompt:"A counter with a plus button, a minus button and a reset button",provider:"anthropic",api_key:$k}')
JOB=$(curl -sS -m 60 -X POST "$API/api/build" -H 'Content-Type: application/json' -d "$BODY")
echo "start: $JOB"
ID=$(echo "$JOB" | jq -r '.job_id // empty'); [ -z "$ID" ] && exit 0
for i in $(seq 1 60); do
  J=$(curl -sS -m 20 "$API/api/jobs/$ID")
  echo "$(date -u +%T) $(echo "$J" | jq -c '{status, stage, builder_mode, steps: (.activity|length), last: (.activity[-3:] // [])}')"
  echo "$J" | jq -e '.status | IN("succeeded","failed","rejected","cancelled")' >/dev/null && { echo "$J" | jq -c '{reason, deploy_url, confidence}'; break; }
  sleep 10
done
