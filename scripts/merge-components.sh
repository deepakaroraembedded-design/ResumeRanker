#!/usr/bin/env bash
# scripts/merge-components.sh — merge component branches in dependency order.
set -euo pipefail

ORDER="C-QA C-04 C-05 C-01 C-02 C-03 C-06 C-07 C-08 C-09 C-11 C-10 C-12 C-13 C-14 C-15"

git checkout main
for id in $ORDER; do
  branch=$(git branch --list --format='%(refname:short)' "feat/$id-*")
  if [ -z "$branch" ]; then
    echo "=== branch for $id not found, skipping ==="
    continue
  fi
  echo "=== merging $branch ==="
  git merge --no-ff --no-commit "$branch" || { echo "CONFLICT in $id"; exit 1; }
  if make gate; then
    git commit -m "merge($id): integrate $branch"
  else
    echo "GATE FAILED after $id — aborting"
    git merge --abort
    exit 1
  fi
done
