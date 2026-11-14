#!/usr/bin/env bash
# Read only: each database, its creation time and the projects connected to it.
set -uo pipefail
API=https://api.vercel.com; Q="teamId=team_71xyHRYPaRkkn2kQ99UT0mDP"; auth=(-H "Authorization: Bearer $VERCEL_TOKEN")
for id in $(curl -sS "${auth[@]}" "$API/v1/storage/stores?$Q" | jq -r '.stores[]?.id'); do
  curl -sS "${auth[@]}" "$API/storage/stores/$id?$Q" | jq -c '(.store // .) | {name, created: (.createdAt/1000 | strftime("%Y-%m-%d %H:%M UTC")), projects: [.projectsMetadata[]? | .name // .projectId]}'
done
