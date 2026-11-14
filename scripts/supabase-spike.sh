#!/usr/bin/env bash
# Read only: is the Supabase access token set, valid, and on the right account?
set -uo pipefail
if [ -z "${SUPABASE_ACCESS_TOKEN:-}" ]; then echo "SUPABASE_ACCESS_TOKEN is not set as a GitHub secret"; exit 0; fi
echo "token starts with: ${SUPABASE_ACCESS_TOKEN:0:4} (length ${#SUPABASE_ACCESS_TOKEN})"
R=$(curl -sS -w '\n%{http_code}' -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" https://api.supabase.com/v1/projects)
CODE=$(echo "$R" | tail -1); BODY=$(echo "$R" | sed '$d')
echo "projects call: $CODE"
echo "$BODY" | jq -r 'if type=="array" then .[] | "\(.name)  ref=\(.id)  status=\(.status)" else . end' 2>/dev/null | head -20
REF=$(echo "$BODY" | jq -r 'if type=="array" then .[] | select(.name=="single-event-rsvp-2043a8") | .id else empty end' 2>/dev/null)
if [ -n "$REF" ]; then
  echo "auth settings readable: $(curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" https://api.supabase.com/v1/projects/$REF/config/auth)"
fi
