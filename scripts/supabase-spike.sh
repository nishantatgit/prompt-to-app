#!/usr/bin/env bash
# Why does inserting a guestbook entry fail? Create a database, migrate it,
# then read and insert through Supabase's REST API with the anon key, the
# way the app does. Prints status codes and error messages, never keys.
set -uo pipefail
API=https://api.vercel.com
TEAM=team_71xyHRYPaRkkn2kQ99UT0mDP
CFG=icfg_OSg4qJPPHnK2vActpSWCUuaE
NAME=vyskar-insert-check
auth=(-H "Authorization: Bearer $VERCEL_TOKEN")
get() { curl -sS "${auth[@]}" "$API$1"; }
post() { curl -sS "${auth[@]}" -H 'Content-Type: application/json' -X POST "$API$1" -d "$2"; }

PID=$(post "/v11/projects?teamId=$TEAM" "{\"name\":\"$NAME\",\"framework\":\"vite\"}" | jq -r '.id // empty')
[ -z "$PID" ] && PID=$(get "/v9/projects/$NAME?teamId=$TEAM" | jq -r .id)
SID=$(post "/v1/storage/stores/integration/direct?teamId=$TEAM" "{\"name\":\"$NAME\",\"integrationConfigurationId\":\"$CFG\",\"integrationProductIdOrSlug\":\"supabase\",\"metadata\":{\"region\":\"bom1\",\"publicEnvVarPrefix\":\"VITE_\"}}" | jq -r '.store.id // empty')
echo "store: ${SID:-FAILED}"; [ -z "$SID" ] && exit 0
post "/v1/integrations/installations/$CFG/resources/$SID/connections?teamId=$TEAM" "{\"projectId\":\"$PID\",\"envVarEnvironments\":[\"production\",\"preview\",\"development\"],\"makeEnvVarsSensitive\":false}" >/dev/null
val() { local id=$(get "/v10/projects/$PID/env?teamId=$TEAM" | jq -r --arg k "$1" '.envs[] | select(.key==$k) | .id' | head -1); get "/v1/projects/$PID/env/$id?teamId=$TEAM" | jq -r .value; }
URL=$(val VITE_SUPABASE_URL); ANON=$(val VITE_SUPABASE_ANON_KEY); PUB=$(val VITE_SUPABASE_PUBLISHABLE_KEY); PG=$(val POSTGRES_URL_NON_POOLING)
echo "anon key starts with: ${ANON:0:3} (length ${#ANON}); publishable starts with: ${PUB:0:12}"
sudo apt-get install -y -qq postgresql-client >/dev/null 2>&1
for i in 1 2 3 4 5 6 7 8; do psql "$PG" -qtAc "select 1" >/dev/null 2>&1 && break; sleep 10; done
echo "migration: $(psql "$PG" -v ON_ERROR_STOP=1 -q -f scripts/001_guestbook.sql 2>&1 | head -3 || true)done"
echo "grants: $(psql "$PG" -tAc "select string_agg(grantee||':'||privilege_type, ', ') from information_schema.role_table_grants where table_name='guestbook_entries'")"
echo "default privileges for anon on public: $(psql "$PG" -tAc "select count(*) from pg_default_acl")"
sleep 5
for KEY in "$ANON" "$PUB"; do
  echo "-- key starting ${KEY:0:6}"
  echo "select: $(curl -sS -w ' %{http_code}' "$URL/rest/v1/guestbook_entries?select=id" -H "apikey: $KEY" -H "Authorization: Bearer $KEY" | cut -c1-300)"
  echo "insert: $(curl -sS -w ' %{http_code}' -X POST "$URL/rest/v1/guestbook_entries" -H "apikey: $KEY" -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' -H 'Prefer: return=minimal' -d '{"name":"Asha","message":"hello"}' | cut -c1-400)"
  echo "insert with apikey only: $(curl -sS -w ' %{http_code}' -X POST "$URL/rest/v1/guestbook_entries" -H "apikey: $KEY" -H 'Content-Type: application/json' -H 'Prefer: return=minimal' -d '{"name":"Asha","message":"hello"}' | cut -c1-400)"
done
echo "rows now: $(psql "$PG" -tAc 'select count(*) from guestbook_entries')"
echo "cleanup: disconnect $(curl -sS -o /dev/null -w '%{http_code}' "${auth[@]}" -X DELETE "$API/v1/storage/stores/$SID/connections?teamId=$TEAM"), delete $(curl -sS -o /dev/null -w '%{http_code}' "${auth[@]}" -X DELETE "$API/v1/storage/stores/integration/$SID?teamId=$TEAM")"
