#!/usr/bin/env bash
# Delete the database the cancelled benchmark run left behind, by exact name.
set -uo pipefail
API=https://api.vercel.com; Q="teamId=team_71xyHRYPaRkkn2kQ99UT0mDP"; auth=(-H "Authorization: Bearer $VERCEL_TOKEN")
ID=$(curl -sS "${auth[@]}" "$API/v1/storage/stores?$Q" | jq -r '.stores[]? | select(.name=="simple-public-guestbook-ca95c2") | .id')
[ -z "$ID" ] && { echo "not found"; exit 0; }
echo "disconnect: $(curl -sS -o /dev/null -w '%{http_code}' "${auth[@]}" -X DELETE "$API/v1/storage/stores/$ID/connections?$Q")"
echo "delete: $(curl -sS -o /dev/null -w '%{http_code}' "${auth[@]}" -X DELETE "$API/v1/storage/stores/integration/$ID?$Q")"
sleep 5
curl -sS "${auth[@]}" "$API/v1/storage/stores?$Q" | jq -r '.stores[]? | .name'
