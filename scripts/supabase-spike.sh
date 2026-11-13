#!/usr/bin/env bash
# Phase 2: how does Vyskar get a new database's keys? Prints only names,
# lengths and statuses, never secret values.
set -uo pipefail
API=https://api.vercel.com
TEAM=team_71xyHRYPaRkkn2kQ99UT0mDP
CFG=icfg_OSg4qJPPHnK2vActpSWCUuaE
auth=(-H "Authorization: Bearer $VERCEL_TOKEN")
get() { curl -sS "${auth[@]}" "$API$1"; }
post() { curl -sS "${auth[@]}" -H 'Content-Type: application/json' -X POST "$API$1" -d "$2"; }

echo "== request schemas"
curl -sS https://vercel.com/openapi.json -o /tmp/openapi.json
for p in '/v1/integrations/installations/{integrationConfigurationId}/resources/{resourceId}/connections' '/v10/projects/{idOrName}/env/{id}' '/v1/projects/{idOrName}/env/{id}'; do
  echo "-- $p"; jq -c --arg p "$p" '.paths[$p] | to_entries[]? | {method: .key, params: [.value.parameters[]?.name], body: .value.requestBody.content["application/json"].schema}' /tmp/openapi.json | cut -c1-1500
done
jq -r '.paths | keys[] | select(test("projects/\\{idOrName\\}/env"))' /tmp/openapi.json

[ "${CREATE:-}" != "1" ] && exit 0
echo "== project"
PROJ=$(post "/v11/projects?teamId=$TEAM" '{"name":"vyskar-db-spike","framework":"vite"}')
PID=$(echo "$PROJ" | jq -r '.id // empty'); [ -z "$PID" ] && PID=$(get "/v9/projects/vyskar-db-spike?teamId=$TEAM" | jq -r .id)
echo "project: $PID"
echo "== store (reuse vyskar-db-spike if it exists)"
SID=$(get "/v1/storage/stores?teamId=$TEAM" | jq -r '.stores[]? | select(.name=="vyskar-db-spike") | .id' | head -1)
if [ -z "$SID" ]; then
  RES=$(post "/v1/storage/stores/integration/direct?teamId=$TEAM" "{\"name\":\"vyskar-db-spike\",\"integrationConfigurationId\":\"$CFG\",\"integrationProductIdOrSlug\":\"supabase\",\"metadata\":{\"region\":\"bom1\",\"publicEnvVarPrefix\":\"VITE_\"}}")
  echo "$RES" | jq -c '{error, id: .store.id, status: .store.status}'
  SID=$(echo "$RES" | jq -r '.store.id // empty')
fi
echo "store: $SID"
STORE=$(get "/storage/stores/$SID?teamId=$TEAM")
RID=$(echo "$STORE" | jq -r '(.store // .) | .externalResourceId')
echo "$STORE" | jq -c '(.store // .) | {status, externalResourceId, targets, projects: [.projectsMetadata[]?.projectId]}'
echo "== read each key by id"
ENVS=$(get "/v10/projects/$PID/env?teamId=$TEAM")
for id in $(echo "$ENVS" | jq -r '.envs[].id'); do
  get "/v1/projects/$PID/env/$id?teamId=$TEAM" | jq -c '{key, type, decrypted, looksPlain: ((.value // "") | startswith("eyJ2Ijoi") | not), valueLength: ((.value // "") | length)}'
done
echo "== try postgres"
URL_ID=$(echo "$ENVS" | jq -r '.envs[] | select(.key=="POSTGRES_URL_NON_POOLING") | .id')
URL=$(get "/v1/projects/$PID/env/$URL_ID?teamId=$TEAM" | jq -r '.value // empty')
case "$URL" in
  postgres*) sudo apt-get install -y -qq postgresql-client >/dev/null 2>&1
             if psql "$URL" -tAc "select 1" >/dev/null 2>&1; then echo "postgres: connected"; else echo "postgres: could not connect"; fi ;;
  *) echo "postgres: the value is not a connection string" ;;
esac
