#!/usr/bin/env bash
# List projects, then delete only the empty test projects by exact name.
set -uo pipefail
API=https://api.vercel.com; Q="teamId=team_71xyHRYPaRkkn2kQ99UT0mDP"; auth=(-H "Authorization: Bearer $VERCEL_TOKEN")
ALL=$(curl -sS "${auth[@]}" "$API/v10/projects?$Q&limit=100" | jq -r '.projects[] | "\(.name) \(.latestDeployments | length)"')
echo "== all projects (name, deployments)"; echo "$ALL"
echo "== deleting"
echo "$ALL" | while read -r name deploys; do
  if [[ "$name" =~ ^(vyskar-db-spike|vyskar-insert-check|guestbook-visitors-leave-[0-9a-f]{6})$ ]] && [ "$deploys" = "0" ]; then
    echo "$name: $(curl -sS -o /dev/null -w '%{http_code}' "${auth[@]}" -X DELETE "$API/v9/projects/$name?$Q")"
  fi
done
