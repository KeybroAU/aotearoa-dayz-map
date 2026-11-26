"""Cut a release from the "## Unreleased" section of CHANGELOG.md.

    python tools/release.py                    # dry run: say what the next release would be
    python tools/release.py --push             # bump the version, commit, tag and push main and the tag
    python tools/release.py --minor --push     # 0.6.x -> 0.7.0 instead of the next patch
    python tools/release.py --revert-to v0.6.2 --push

Before anything changes it runs `nz_food.py --verify` (food textures, config and script up to date,
right sizes, no blank pack fronts); look over preview/nz_food_layouts.png too. The tag push starts
.github/workflows/release.yml, which builds and publishes the GitHub release.
Releases are never replaced: the script refuses a version whose tag already exists, and the workflow
refuses to publish over an existing release. --revert-to puts the files back as they were at an
older tag and releases that as a new version, so every earlier release stays downloadable.
"""
import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
VERSION = ROOT / "VERSION"
MOD_FILES = [ROOT / "mod" / "mod.cpp", ROOT / "mapitem" / "mod.cpp"]
# Release bookkeeping and tooling that a revert keeps at its current state, so the version keeps
# going up and the release safeguards survive.
KEEP_ON_REVERT = ["CHANGELOG.md", "VERSION", "mod/mod.cpp", "mapitem/mod.cpp", "tools/release.py",
                  "tools/backup_releases.py", ".github/workflows/release.yml"]
UNRELEASED = re.compile(r"^## Unreleased[ \t]*\n(.*?)(?=^## |\Z)", re.M | re.S)


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, check=check, capture_output=True, text=True).stdout.strip()


def unreleased_notes(text):
    m = UNRELEASED.search(text)
    return m.group(1).strip() if m else ""


def bump(version, minor):
    major, mi, patch = (int(p) for p in version.split("."))
    return f"{major}.{mi + 1}.0" if minor else f"{major}.{mi}.{patch + 1}"


def tag_exists(tag):
    if git("tag", "-l", tag):
        return True
    return bool(git("ls-remote", "--tags", "origin", f"refs/tags/{tag}", check=False))


def revert_to(tag):
    if not git("tag", "-l", tag):
        sys.exit(f"No tag {tag}")
    git("restore", f"--source={tag}", "--staged", "--worktree", "--", ":/")
    git("restore", "--source=HEAD", "--staged", "--worktree", "--", *KEEP_ON_REVERT)
    text = CHANGELOG.read_text(encoding="utf-8")
    entry = (f"## Unreleased\n\n- Reverted the map to {tag}: everything except the release tooling is back as it "
             f"was in that release, so changes made since {tag} are undone\n\n")
    # Unreleased notes describe changes the revert just undid.
    text = UNRELEASED.sub("", text, count=1)
    text = re.sub(r"^## ", lambda m: entry + "## ", text, count=1, flags=re.M)
    CHANGELOG.write_text(text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--push", action="store_true", help="commit, tag and push (default is a dry run)")
    ap.add_argument("--minor", action="store_true", help="bump the minor version instead of the patch")
    ap.add_argument("--revert-to", metavar="TAG", help="release the files from an older tag as a new version")
    args = ap.parse_args()

    if args.push and git("status", "--porcelain"):
        sys.exit("The working tree has uncommitted changes; commit or stash them first")
    if args.push and git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        sys.exit("Releases are cut from main")
    if args.revert_to:
        if not args.push:
            print(f"Would restore the files from {args.revert_to} and release them as a new version")
            return
        revert_to(args.revert_to)

    text = CHANGELOG.read_text(encoding="utf-8")
    notes = unreleased_notes(text)
    if not notes:
        print("Nothing to release: CHANGELOG.md has no Unreleased changes")
        return
    pre = subprocess.run([sys.executable, str(ROOT / "tools" / "nz_food.py"), "--verify"], cwd=ROOT)
    if pre.returncode:
        sys.exit("Food textures failed the pre-release check; fix them before releasing")
    old = VERSION.read_text().strip()
    new = bump(old, args.minor)
    tag = f"v{new}"
    if tag_exists(tag):
        sys.exit(f"{tag} already exists; releases are never replaced")
    print(f"{old} -> {new}\n\n{notes}\n")
    if not args.push:
        print("Dry run; pass --push to release")
        return

    today = datetime.date.today().isoformat()
    CHANGELOG.write_text(UNRELEASED.sub(lambda m: f"## {new} - {today}\n{m.group(1)}", text, count=1), encoding="utf-8")
    VERSION.write_text(new + "\n")
    for f in MOD_FILES:
        f.write_text(re.sub(r'(version\s*=\s*")[^"]+(")', rf"\g<1>{new}\g<2>", f.read_text(), count=1))
    subprocess.run([sys.executable, str(ROOT / "tools" / "check_map.py")], cwd=ROOT, check=True)
    git("add", "-A")
    git("commit", "-m", f"Release {new}")
    git("tag", "-a", tag, "-m", f"Aotearoa {tag}")
    git("push", "origin", "main")
    git("push", "origin", tag)
    print(f"Pushed {tag}; GitHub is building the release")


if __name__ == "__main__":
    main()
