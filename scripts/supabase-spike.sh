#!/usr/bin/env bash
# Read only: databases on the account, and whether the Supabase token works.
set -uo pipefail
curl -sS -H "Authorization: Bearer $VERCEL_TOKEN" "https://api.vercel.com/v1/storage/stores?teamId=team_71xyHRYPaRkkn2kQ99UT0mDP" | jq -r '"databases: " + ([.stores[]?.name] | join(", "))'
if [ -z "${SUPABASE_ACCESS_TOKEN:-}" ]; then echo "SUPABASE_ACCESS_TOKEN: not set on GitHub"; exit 0; fi
echo "SUPABASE_ACCESS_TOKEN: projects call $(curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" https://api.supabase.com/v1/projects)"
