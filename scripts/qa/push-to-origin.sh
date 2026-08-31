#!/usr/bin/env bash
# Push the local ATS-Scan commit to origin using the github-personal SSH key.
# This script is a one-shot helper; it starts its own ssh-agent and kills it on exit.
set -euo pipefail

cd "$(dirname "$0")/../.."

SSH_KEY="${HOME}/.ssh/id_publicgithub"
HOST_ALIAS="github-personal"
REMOTE_URL="${HOST_ALIAS}:deepakaroraembedded-design/ResumeRanker.git"
HTTPS_URL="https://github.com/deepakaroraembedded-design/ResumeRanker.git"

if [[ ! -f "${SSH_KEY}" ]]; then
    echo "ERROR: SSH key not found: ${SSH_KEY}"
    exit 1
fi

# Start a private ssh-agent for this push so the key is only unlocked briefly.
echo "==> Starting ssh-agent for this push..."
eval "$(ssh-agent -s)"
trap 'ssh-agent -k >/dev/null 2>&1 || true' EXIT

echo "==> Adding ${SSH_KEY} (enter the passphrase when prompted)..."
ssh-add "${SSH_KEY}"

echo "==> Testing GitHub authentication with ${HOST_ALIAS}..."
ssh_output=$(ssh -T -o IdentitiesOnly=yes "${HOST_ALIAS}" 2>&1) || true

if echo "${ssh_output}" | grep -q "successfully authenticated"; then
    echo "    OK: ${ssh_output}"
    git remote set-url origin "${REMOTE_URL}"
else
    echo "    SSH auth test output: ${ssh_output}"
    echo "    Could not confirm SSH write access. Falling back to HTTPS + token."
    git remote set-url origin "${HTTPS_URL}"
    echo ""
    echo "Run the push with:"
    echo "    git push origin main"
    echo "When prompted, use your GitHub username and a personal access token as the password."
    echo ""
    exit 0
fi

echo "==> Remote origin is now set to:"
git remote -v

echo ""
echo "==> Commits that will be pushed:"
git log origin/main..HEAD --oneline

echo ""
# Offer to commit the status files that are currently uncommitted.
status_files_uncommitted=false
if git status --short | grep -qE '^ M docs/qa/metrics.csv'; then
    status_files_uncommitted=true
fi
if git status --short | grep -qE '^\?\? docs/qa/STATUS.md'; then
    status_files_uncommitted=true
fi

if [[ "${status_files_uncommitted}" == true ]]; then
    read -r -p "Commit docs/qa/metrics.csv and docs/qa/STATUS.md before pushing? [y/N] " ans
    if [[ "${ans:-n}" =~ ^[Yy]$ ]]; then
        git add docs/qa/metrics.csv docs/qa/STATUS.md
        git commit -m "docs: C-QA status snapshot and corrected metrics"
        echo "==> Committed the status files."
    fi
fi

if git status --short | grep -qE '^\?\? TESTDATA/'; then
    echo ""
    echo "WARNING: untracked TESTDATA/ exists. It will NOT be committed."
fi

echo ""
echo "==> Pushing..."
git push origin main

echo ""
echo "==> Push complete."
