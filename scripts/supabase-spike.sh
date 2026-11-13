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
echo "== connect"
for body in "{\"projectId\":\"$PID\"}" "{\"projectId\":\"$PID\",\"environments\":[\"production\",\"preview\",\"development\"]}"; do
  for rid in "$SID" "$RID"; do
    R=$(post "/v1/integrations/installations/$CFG/resources/$rid/connections?teamId=$TEAM" "$body")
    echo "resource=$rid body=$body -> $(echo "$R" | jq -c '{error: .error.message} // .' | cut -c1-300)"
  done
done
echo "== project env vars"
get "/v10/projects/$PID/env?teamId=$TEAM&decrypt=true" | jq -c '[.envs[]? | {key, type, target, valueLength: (.value // "" | length), decrypted}]'
echo "== try postgres"
URL=$(get "/v10/projects/$PID/env?teamId=$TEAM&decrypt=true" | jq -r '.envs[]? | select(.key=="POSTGRES_URL_NON_POOLING") | .value' | head -1)
if [ -n "$URL" ] && [ "${#URL}" -gt 20 ]; then
  sudo apt-get install -y -qq postgresql-client >/dev/null 2>&1
  psql "$URL" -tAc "select 'connected', current_database(), version()" 2>&1 | cut -c1-120
else
  echo "no usable POSTGRES_URL_NON_POOLING value (length ${#URL})"
fi
