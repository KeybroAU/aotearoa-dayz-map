#!/usr/bin/env bash
# Copy every vX.Y.Z release's files into the "release-archive" release, so each version stays
# downloadable even if its own release is deleted or edited. Files already in the archive are
# skipped. Needs the GitHub CLI with GH_TOKEN set (the workflows pass their own token).
#
# With BACKUP_REPO (owner/name, a repo with at least one commit) and BACKUP_TOKEN (a token that can
# write to it), it also mirrors each release into that repo, as a second copy outside this one.
set -euo pipefail

ARCHIVE=release-archive
if ! gh release view "$ARCHIVE" >/dev/null 2>&1; then
  gh release create "$ARCHIVE" --prerelease --latest=false --title "Release archive (backups)" \
    --notes "Backup copies of every Aotearoa release's files, kept in case a release has to be restored. Download the current version from the latest release instead."
fi
have=$(gh release view "$ARCHIVE" --json assets -q '.assets[].name')
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

for tag in $(gh release list --limit 500 --json tagName -q '.[].tagName' | grep -E '^v[0-9]'); do
  for name in $(gh release view "$tag" --json assets -q '.assets[].name'); do
    # Asset names carry the version, except the checksum file.
    out="$name"
    [ "$name" = "SHA256SUMS" ] && out="aotearoa-${tag#v}-SHA256SUMS"
    if grep -qxF "$out" <<<"$have"; then continue; fi
    rm -rf "$work/dl" && mkdir -p "$work/dl"
    gh release download "$tag" -p "$name" -D "$work/dl"
    mv "$work/dl/$name" "$work/$out"
    gh release upload "$ARCHIVE" "$work/$out"
    rm -f "$work/$out"
    echo "archived $tag/$name as $out"
  done
done

if [ -n "${BACKUP_REPO:-}" ] && [ -n "${BACKUP_TOKEN:-}" ]; then
  for tag in $(gh release list --limit 500 --json tagName -q '.[].tagName' | grep -E '^v[0-9]'); do
    if GH_TOKEN="$BACKUP_TOKEN" gh release view "$tag" -R "$BACKUP_REPO" >/dev/null 2>&1; then continue; fi
    rm -rf "$work/m" && mkdir -p "$work/m"
    gh release download "$tag" -D "$work/m"
    gh release view "$tag" --json body -q .body >"$work/notes.md"
    GH_TOKEN="$BACKUP_TOKEN" gh release create "$tag" "$work"/m/* -R "$BACKUP_REPO" \
      --title "Aotearoa $tag" --notes-file "$work/notes.md" --latest=false
    echo "mirrored $tag to $BACKUP_REPO"
  done
fi
echo "Release archive up to date"
