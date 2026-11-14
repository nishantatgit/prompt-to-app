#!/usr/bin/env bash
# Read only: does the live frontend have the Cancel button?
for host in app.vyskar.com; do
  JS=$(curl -sS -m 20 "https://$host/" | grep -o 'src="/assets/[^"]*\.js"' | head -1 | cut -d'"' -f2)
  B=$(curl -sS -m 20 "https://$host$JS")
  echo "$host bundle $JS"
  for s in "Cancel build" "Waiting for a free builder" "Build steps"; do printf "  %-28s %s\n" "$s" "$(echo "$B" | grep -c "$s")"; done
  curl -sSI -m 20 "https://$host/" | grep -iE "^(age|last-modified|x-vercel-id|date):"
done
