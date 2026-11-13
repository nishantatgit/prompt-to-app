#!/usr/bin/env bash
# Delete only the databases the spikes created, to check the delete calls.
set -uo pipefail
API=https://api.vercel.com
TEAM=team_71xyHRYPaRkkn2kQ99UT0mDP
auth=(-H "Authorization: Bearer $VERCEL_TOKEN")
echo "== before"
curl -sS "${auth[@]}" "$API/v1/storage/stores?teamId=$TEAM" | jq -c '[.stores[]? | {id, name, product: .product.slug}]'
for id in $(curl -sS "${auth[@]}" "$API/v1/storage/stores?teamId=$TEAM" | jq -r '.stores[]? | select(.name | test("^(vyskar-spike-|vyskar-db-spike$|guestbook-)")) | .id'); do
  echo "-- $id"
  echo "disconnect: $(curl -sS -o /dev/null -w '%{http_code}' "${auth[@]}" -X DELETE "$API/v1/storage/stores/$id/connections?teamId=$TEAM")"
  echo "delete: $(curl -sS -w ' %{http_code}' "${auth[@]}" -X DELETE "$API/v1/storage/stores/integration/$id?teamId=$TEAM" | cut -c1-300)"
done
sleep 10
echo "== after"
curl -sS "${auth[@]}" "$API/v1/storage/stores?teamId=$TEAM" | jq -c '[.stores[]? | {id, name, product: .product.slug}]'
