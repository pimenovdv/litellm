#!/usr/bin/env bash
set -euo pipefail

target="$1"
decision="skip"

while IFS= read -r file; do
  if [[ "$target" == "backend" ]]; then
    if [[ "$file" != ui/* && "$file" != *.md && "$file" != *.mdx ]]; then
      decision="run"
      break
    fi
  else
    decision="run"
    break
  fi
done

echo "$decision"
