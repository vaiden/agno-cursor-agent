#!/usr/bin/env bash
# Sync local default branch after a PR merge. Run from repo root.
# Usage: ./scripts/sync-main-after-merge.sh [merged-branch-to-delete]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: $ROOT" >&2
  exit 1
fi

DEFAULT_BRANCH="$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || true)"
if [[ -z "$DEFAULT_BRANCH" ]]; then
  if git show-ref --verify --quiet refs/heads/main; then
    DEFAULT_BRANCH=main
  elif git show-ref --verify --quiet refs/heads/master; then
    DEFAULT_BRANCH=master
  else
    echo "Could not determine default branch (main/master)." >&2
    exit 1
  fi
fi

PREV="$(git branch --show-current 2>/dev/null || true)"
TO_DELETE="${1:-}"

echo "Fetching origin…"
git fetch origin --prune

echo "Checking out $DEFAULT_BRANCH…"
git checkout "$DEFAULT_BRANCH"

echo "Pulling latest $DEFAULT_BRANCH…"
git pull --ff-only origin "$DEFAULT_BRANCH"

if [[ -n "$TO_DELETE" ]]; then
  if [[ "$TO_DELETE" != "$DEFAULT_BRANCH" ]]; then
    echo "Deleting local branch $TO_DELETE (if merged)…"
    git branch -d "$TO_DELETE" 2>/dev/null || git branch -D "$TO_DELETE" 2>/dev/null || true
  fi
elif [[ -n "$PREV" && "$PREV" != "$DEFAULT_BRANCH" ]]; then
  echo "Deleting previous branch $PREV (if merged)…"
  git branch -d "$PREV" 2>/dev/null || true
fi

echo "On $(git branch --show-current) @ $(git rev-parse --short HEAD)"
