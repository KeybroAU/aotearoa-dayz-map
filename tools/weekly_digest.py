"""The weekly Discord digest: the week's releases and what changed in them, how many commits landed,
and what's waiting under Unreleased.

    python tools/weekly_digest.py            # print the Discord payload (JSON)
    python tools/weekly_digest.py --days 14  # cover a longer window

.github/workflows/discord-weekly.yml runs it every Sunday morning (New Zealand time) and posts the
result with the DISCORD_WEBHOOK secret. It prints nothing when nothing happened that week.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/KeybroAU/aotearoa-dayz-map"
SECTION = re.compile(r"^## (\S+)[^\n]*\n(.*?)(?=^## |\Z)", re.M | re.S)
LIMIT = 3800  # Discord allows 4096 characters in an embed description


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def changelog() -> dict[str, str]:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return {m.group(1): m.group(2).strip() for m in SECTION.finditer(text)}


def bullets(body: str, limit: int = 6) -> list[str]:
    items = [ln[2:].strip() for ln in body.splitlines() if ln.startswith("- ")]
    out = []
    for it in items[:limit]:
        it = re.sub(r"`([^`]*)`", r"\1", it)
        out.append("• " + (it if len(it) <= 180 else it[:177].rsplit(" ", 1)[0] + "..."))
    if len(items) > limit:
        out.append(f"• and {len(items) - limit} more")
    return out


def digest(days: int) -> dict | None:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    tags = []
    for line in git("for-each-ref", "--sort=creatordate", "--format=%(refname:short) %(creatordate:iso-strict)",
                    "refs/tags/v*").splitlines():
        name, when = line.split(" ", 1)
        if datetime.fromisoformat(when) >= since:
            tags.append(name)
    commits = git("rev-list", "--count", f"--since={since.isoformat()}", "HEAD")
    notes = changelog()
    if not tags and int(commits) == 0:
        return None
    parts = []
    for tag in reversed(tags):
        body = notes.get(tag.lstrip("v"), "")
        parts.append(f"**[{tag}]({REPO}/releases/tag/{tag})**\n" + "\n".join(bullets(body) or ["• (no notes)"]))
    waiting = notes.get("Unreleased")
    if waiting:
        parts.append("**Coming in the next release**\n" + "\n".join(bullets(waiting, 4)))
    text = ""
    for p in parts:
        if len(text) + len(p) + 2 > LIMIT:
            text += f"\n\nMore in the [changelog]({REPO}/blob/main/CHANGELOG.md)."
            break
        text += ("\n\n" if text else "") + p
    latest = git("describe", "--tags", "--abbrev=0", "--match", "v*")
    title = f"Aotearoa this week: {len(tags)} release{'s' if len(tags) != 1 else ''}, {commits} commits"
    return {"username": "Aotearoa GitHub", "allowed_mentions": {"parse": []},
            "embeds": [{"title": title, "url": f"{REPO}/releases/tag/{latest}", "color": 3066993,
                        "description": text or "Work in progress, no release this week.",
                        "footer": {"text": f"Latest: {latest} · Designed by Keybro · keybrogaming.com"}}]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    payload = digest(ap.parse_args().days)
    if payload:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
