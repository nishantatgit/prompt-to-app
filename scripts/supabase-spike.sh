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
echo "== build the stub app with this database"
W=/tmp/app && rm -rf $W && git show origin/feat/supabase-build:backend/templates/react-vite/package.json >/dev/null 2>&1
git fetch -q origin feat/supabase-build && mkdir -p $W && git archive origin/feat/supabase-build backend/templates/react-vite | tar -x -C /tmp && cp -r /tmp/backend/templates/react-vite/. $W/
mkdir -p $W/src/lib $W/tests && cp scripts/guestbook/guestbook.jsx $W/src/App.jsx && cp scripts/guestbook/supabase.js $W/src/lib/supabase.js
printf "VITE_SUPABASE_URL=%s\nVITE_SUPABASE_ANON_KEY=%s\n" "$URL" "$ANON" > $W/.env.local
jq -r '.e2e_tests[] | select(.id=="E2") | .code' scripts/guestbook/test_planner.json > $W/tests/e2.spec.js
cd $W && yarn install --silent >/dev/null 2>&1 && yarn -s build >/dev/null 2>&1 && echo "built" && npx playwright install --with-deps chromium >/dev/null 2>&1
PORT=4300 yarn -s playwright test --reporter=line 2>&1 | grep -vE "^\s*$" | tail -12
for f in test-results/*/error-context.md; do echo "== $f"; sed -n '/Page snapshot/,$p' "$f" | head -40; done
cd - >/dev/null
echo "cleanup: disconnect $(curl -sS -o /dev/null -w '%{http_code}' "${auth[@]}" -X DELETE "$API/v1/storage/stores/$SID/connections?teamId=$TEAM"), delete $(curl -sS -o /dev/null -w '%{http_code}' "${auth[@]}" -X DELETE "$API/v1/storage/stores/integration/$SID?teamId=$TEAM")"
