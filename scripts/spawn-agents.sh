#!/usr/bin/env bash
# scripts/spawn-agents.sh — create one git worktree per component agent.
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
PARENT="$ROOT/../ats-agents"
FREEZE="contracts-frozen"

git rev-parse --verify "$FREEZE" >/dev/null || { echo "Wave 0 not tagged"; exit 1; }
mkdir -p "$PARENT"

while IFS=: read -r id slug; do
  [[ "$id" =~ ^# ]] && continue
  wt="$PARENT/$id"
  [ -d "$wt" ] && { echo "skip $id"; continue; }
  git worktree add -b "feat/$id-$slug" "$wt" "$FREEZE"
  (
    cd "$wt"
    export PATH="$HOME/.local/bin:$PATH"
    uv sync --frozen
  )
  echo "ready: $wt  (branch feat/$id-$slug)"
done < "$ROOT/scripts/components.txt"
