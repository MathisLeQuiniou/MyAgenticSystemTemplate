#!/usr/bin/env bash
# Merge a GitHub .zip of the template into the current branch.
#
# Usage: ./sync-from-template.sh path/to/template.zip
#
# Each zip is stored as a commit on a local "template-upstream" branch, which
# is then merged into the current branch. Thanks to that branch, git knows
# what changed in the template since the previous import: only those changes
# are applied, and conflicts are left for you to resolve.
# (On the very first run there is no previous import, so every file that
# differs between the zip and your branch shows up as a conflict.)
set -euo pipefail

MIRROR="template-upstream"

[ $# -eq 1 ] && [ -f "$1" ] || { echo "Usage: $0 path/to/template.zip"; exit 1; }
ZIP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"

cd "$(git rev-parse --show-toplevel)"
git diff --quiet && git diff --cached --quiet || { echo "Commit or stash your changes first."; exit 1; }

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# Extract the zip; GitHub wraps everything in a single <repo>-<ref>/ folder.
unzip -q "$ZIP" -d "$TMP/src"
SRC="$TMP/src"
[ "$(ls -A "$SRC" | wc -l)" -eq 1 ] && [ -d "$SRC/$(ls -A "$SRC")" ] && SRC="$SRC/$(ls -A "$SRC")"

# GitHub writes the template commit SHA in the zip comment.
SHA=$(unzip -z "$ZIP" | grep -Eo '[0-9a-f]{40}' | head -n1 || true)
LABEL="${SHA:0:7}"; LABEL="${LABEL:-$(basename "$ZIP")}"

# Snapshot the zip content as a commit on the mirror branch
# (temporary index: your working tree is not touched).
GIT_DIR_ABS=$(cd "$(git rev-parse --git-dir)" && pwd)
export GIT_INDEX_FILE="$TMP/index"
(cd "$SRC" && git --git-dir="$GIT_DIR_ABS" --work-tree=. add -A -f .)
TREE=$(git write-tree)
unset GIT_INDEX_FILE

PARENT=$(git rev-parse -q --verify "refs/heads/$MIRROR" || true)
if [ -z "$PARENT" ] || [ "$TREE" != "$(git rev-parse "$PARENT^{tree}")" ]; then
  COMMIT=$(git commit-tree "$TREE" ${PARENT:+-p "$PARENT"} -m "template: $LABEL")
  git update-ref "refs/heads/$MIRROR" "$COMMIT"
fi

# Merge it into the current branch.
if git merge --allow-unrelated-histories --no-ff --no-edit -m "Merge template $LABEL" "$MIRROR"; then
  echo "Done. Push the mirror branch too: git push origin $MIRROR"
else
  echo
  echo "Resolve the conflicts above, then: git add <files> && git commit --no-edit"
  echo "Or cancel with: git merge --abort"
  exit 1
fi
