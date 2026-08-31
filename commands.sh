#!/usr/bin/env bash
# commands.sh — Reference commands for RESUME-RANKER Netflix (JR41108) scoring
#
# Usage:  bash commands.sh <command>
# Commands:
#   run           Run with the original JD in offline mode (local logic only)
#   ats           Run with the ATS-aligned JobSpec + config (local logic only)
#   compile-jd    Compile the ATS-aligned JobSpec for review
#   gate          Run the test suite and gate
#
# LLM / API-key mode has been removed; all scoring runs use local deterministic
# logic and local embeddings.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

cmd="${1:-help}"

case "$cmd" in
  run)
    uv run resume-ranker run \
      --resumes TESTDATA/NETFLIX \
      --jd TESTDATA/NETFLIX/jd.txt \
      --out TESTDATA/NETFLIX/out \
      --mode offline \
      --force
    ;;

  ats)
    uv run resume-ranker run \
      --resumes TESTDATA/NETFLIX \
      --jd TESTDATA/NETFLIX/netflix_ats_jobspec.yaml \
      --config TESTDATA/NETFLIX/netflix_ats_config.yaml \
      --out TESTDATA/NETFLIX/out_ats_matched \
      --mode offline \
      --force
    ;;

  compile-jd)
    uv run resume-ranker compile-jd \
      --jd TESTDATA/NETFLIX/netflix_ats_jobspec.yaml \
      --out TESTDATA/NETFLIX/netflix_ats_jobspec_compiled.json
    ;;

  gate)
    make gate
    ;;

  help|*)
    echo "Usage: bash commands.sh <command>"
    echo "Commands: run, ats, compile-jd, gate"
    ;;
esac
