#!/usr/bin/env bash
# Checks that Vyskar can create a Supabase database through Vercel's API.
# Prints only IDs, names and statuses, never secret values.
set -uo pipefail
API=https://api.vercel.com
auth=(-H "Authorization: Bearer $VERCEL_TOKEN")
get() { curl -sS "${auth[@]}" "$API$1"; }

echo "== user and default team"
get /v2/user | jq '{username: .user.username, defaultTeamId: .user.defaultTeamId}'
TEAM=$(get /v2/user | jq -r '.user.defaultTeamId // empty')
Q=${TEAM:+?teamId=$TEAM}
echo "== teams"
get /v2/teams | jq '[.teams[]? | {id, slug, name}]'

echo "== integration configurations"
for q in "view=account&teamId=$TEAM" "view=project&teamId=$TEAM" "view=account" "view=account&installationType=marketplace&teamId=$TEAM"; do
  echo "-- $q"; get "/v1/integrations/configurations?$q" | jq -c '[.[]? | {id, slug, integrationId, installationType, source}] // .'
done
echo "-- stores"; get "/v1/storage/stores$Q" | jq -c '[.stores[]? | {id, name, type, product: .product.slug}] // .'
CONFIGS=$(for q in "view=account&teamId=$TEAM" "view=project&teamId=$TEAM"; do get "/v1/integrations/configurations?$q"; done | jq -s 'add')
echo "$CONFIGS" | jq '[.[]? | {id, slug, integrationId, ownerId, source}] // .'
CFG=$(echo "$CONFIGS" | jq -r '[.[]? | select(.slug | test("supabase"; "i"))][0].id // empty')
echo "supabase configuration: ${CFG:-NOT FOUND}"
[ -z "$CFG" ] && exit 0

echo "== products"
PRODUCTS=$(get "/v1/integrations/configuration/$CFG/products$Q")
echo "$PRODUCTS" | jq '[.products[]? | {id, slug, name, protocols: (.protocols|keys?)}] // .'
PRODUCT=$(echo "$PRODUCTS" | jq -r '.products[0].slug // .products[0].id // empty')

echo "== storage endpoints in the OpenAPI spec"
curl -sS https://vercel.com/openapi.json -o /tmp/openapi.json
jq -r '.paths | to_entries[] | select(.key | test("storage/stores|integrations/installations/.*/resources")) | .key as $p | .value | keys[] | "\(.) \($p)"' /tmp/openapi.json | grep -iv parameters

[ "${CREATE:-}" != "1" ] && exit 0
echo "== create a test store"
NAME="vyskar-spike-$(date +%s)"
RES=$(curl -sS "${auth[@]}" -H 'Content-Type: application/json' -X POST "$API/v1/storage/stores/integration/direct$Q" \
  -d "{\"name\":\"$NAME\",\"integrationConfigurationId\":\"$CFG\",\"integrationProductIdOrSlug\":\"$PRODUCT\"}")
echo "$RES" | jq '{error, store: (.store | if . then {id, name, status, externalResourceId, billingPlan: .billingPlan.name, secretNames: [.secrets[]?.name]} else null end)}'
echo "$RES" | jq -r '.store.id // empty' > /tmp/store_id
