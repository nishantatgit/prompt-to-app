#!/usr/bin/env bash
# List the Supabase databases on the account. Read only.
set -uo pipefail
curl -sS -H "Authorization: Bearer $VERCEL_TOKEN" "https://api.vercel.com/v1/storage/stores?teamId=team_71xyHRYPaRkkn2kQ99UT0mDP" \
  | jq -r '.stores[]? | select(.product.slug=="supabase" or .type=="integration") | "\(.name)  created \(.createdAt/1000 | strftime("%H:%M UTC"))"'
