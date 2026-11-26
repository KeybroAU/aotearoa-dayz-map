"""Copy every GitHub release's files to a backup folder, so an old version can be restored even if a
release is deleted from GitHub.

    python tools/backup_releases.py /path/to/backups

Each release goes in <folder>/<tag>/ with its notes and a SHA256SUMS file. Files that are already
backed up with the right size are skipped, so it is cheap to run after every release. Set
GITHUB_TOKEN to avoid the API's anonymous rate limit.
"""
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = "KeybroAU/aotearoa-dayz-map"


def get(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "aotearoa-backup"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    return urllib.request.urlopen(req, timeout=120)


def releases():
    page = 1
    while True:
        batch = json.load(get(f"https://api.github.com/repos/{REPO}/releases?per_page=100&page={page}"))
        if not batch:
            return
        yield from batch
        page += 1


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = Path(sys.argv[1])
    for rel in releases():
        if not re.match(r"v\d", rel["tag_name"]):
            continue
        folder = root / rel["tag_name"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "notes.md").write_text((rel.get("body") or "") + "\n", encoding="utf-8")
        new = 0
        for asset in rel["assets"]:
            dest = folder / asset["name"]
            if dest.exists() and dest.stat().st_size == asset["size"]:
                continue
            tmp = dest.with_suffix(dest.suffix + ".part")
            with get(asset["url"], "application/octet-stream") as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            tmp.replace(dest)
            new += 1
        sums = [f"{sha256(p)}  {p.name}" for p in sorted(folder.iterdir()) if p.name not in ("SHA256SUMS", "notes.md")]
        (folder / "SHA256SUMS").write_text("\n".join(sums) + "\n")
        print(f"{rel['tag_name']}: {len(rel['assets'])} files ({new} new)")


if __name__ == "__main__":
    main()
