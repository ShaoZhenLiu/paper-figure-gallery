#!/usr/bin/env python3
"""Stage the gallery and its overflow images without checking out either release branch."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

from gallery_extension.catalog import CACHE, ROOT, VENUES, Catalog, paper_key
from validate_gallery import VALID_PATTERNS


PAGE_BUDGET = 940_000_000
SITE_FILES = frozenset({
    "index.html", "support.html", "LICENSE", "NOTICE.md", "IMAGES_POLICY.md",
    "assets/app.js", "assets/style.css", "assets/figures.js", "assets/i18n.js",
    "assets/i18n_gallery.js", "assets/support-dialog.css", "assets/support-dialog.js",
    "assets/alipay-pay.jpg", "assets/wechat-pay.jpg",
    "data/figures.json", "data/gallery_distinctions.json",
})
ASSETS_BRANCH = "gallery-assets"
PAGES_BRANCH = "gh-pages"
ADDITIONS = "gallery-local/figures.js"
VERSIONED_FILES = ("assets/app.js", "assets/style.css", "assets/i18n_gallery.js", ADDITIONS)


def git(*args, payload=None, env=None):
    return subprocess.run(
        ["git", *args], cwd=ROOT, input=payload, env=env, check=True,
        stdout=subprocess.PIPE,
    ).stdout


def tree_files(revision):
    files = {}
    for record in git("ls-tree", "-r", "-l", "-z", revision).split(b"\0"):
        if record:
            header, filename = record.split(b"\t", 1)
            mode, kind, digest, size = header.split()
            if kind == b"blob":
                files[filename.decode("utf-8")] = (mode, digest, int(size))
    return files


def parents_for(branch):
    output = git("for-each-ref", "--format=%(objectname)", f"refs/heads/{branch}",
                 f"refs/remotes/origin/{branch}").decode().splitlines()
    return output[:1]


def stage(branch, base, media, generated, message):
    entries = dict(base)
    for path, contents in generated.items():
        digest = git("hash-object", "-w", "--stdin", payload=contents).strip()
        entries[path] = (b"100644", digest, len(contents))

    with tempfile.TemporaryDirectory(prefix="release-index-", dir=CACHE) as scratch:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(scratch) / "index")}
        git("read-tree", "--empty", env=env)
        records = b"".join(mode + b" " + digest + b"\t" + path.encode() + b"\0"
                           for path, (mode, digest, _) in entries.items())
        if records:
            git("update-index", "-z", "--index-info", env=env, payload=records)
        if media:
            paths = b"".join(path.encode() + b"\0" for path in media)
            git("add", "-f", "--pathspec-from-file=-", "--pathspec-file-nul", env=env, payload=paths)
        tree = git("write-tree", env=env).strip().decode()

    staged = tree_files(tree)
    if staged.keys() != entries.keys() | media.keys():
        raise ValueError(f"The {branch} tree does not match its manifest")
    for path, size in media.items():
        if staged[path][2] != size:
            raise ValueError(f"Image size changed while staging: {path}")
    parents = parents_for(branch)
    if parents and git("rev-parse", f"{parents[0]}^{{tree}}").strip().decode() == tree:
        commit = parents[0]
    else:
        parent = ["-p", parents[0]] if parents else []
        commit = git("commit-tree", tree, *parent, "-m", message).strip().decode()
    return commit, sum(row[2] for row in staged.values())


def catalog_rows(snapshot):
    if snapshot:
        return [row for row in json.loads(snapshot.read_bytes()) if row["venue"] in VENUES]
    catalog = Catalog()
    try:
        return catalog.publish(strict=True)
    finally:
        catalog.db.close()


def sizes_for(rows, curated):
    ids = {row["id"] for row in curated}
    papers = {paper_key(row) for row in curated}
    images = {}
    for row in rows:
        path = Path(row["image"])
        key = paper_key(row)
        if row["id"] in ids or key in papers or path.as_posix() in images:
            raise ValueError(f"Duplicate gallery record: {row['id']}")
        if path.is_absolute() or ".." in path.parts or path.parts[:2] != ("gallery-local", "images"):
            raise ValueError(f"Invalid gallery image: {path}")
        if row.get("pattern") not in VALID_PATTERNS or row.get("excluded_reason"):
            raise ValueError(f"Figure needs review before release: {row['id']}")
        images[path.as_posix()] = (ROOT / path).stat().st_size
        ids.add(row["id"])
        papers.add(key)
    return images


def build(repo, snapshot):
    CACHE.mkdir(exist_ok=True)
    index = git("show", "HEAD:index.html")
    curated = json.loads(git("show", "HEAD:data/figures.json"))
    relative_curated = {row["image"] for row in curated}
    source = tree_files("HEAD")
    base = {path: source[path] for path in SITE_FILES | relative_curated}
    rows = catalog_rows(snapshot)
    sizes = sizes_for(rows, curated)

    # Reserve enough space for the index after absolute asset URLs are added.
    reserve = len(json.dumps(rows, ensure_ascii=True).encode()) + 160 * len(rows) + 8192
    remaining = PAGE_BUDGET - sum(row[2] for row in base.values()) - reserve
    if remaining < 0:
        raise ValueError("The curated gallery and index exceed the Pages size budget")
    old_pages = parents_for(PAGES_BRANCH)
    old_site = tree_files(old_pages[0]) if old_pages else {}
    local, overflow = {}, {}
    for path in sorted(sizes, key=lambda path: (path not in old_site, path)):
        size = sizes[path]
        if size <= remaining:
            local[path] = size
            remaining -= size
        else:
            overflow[path] = size

    assets, asset_bytes = stage(
        ASSETS_BRANCH, {}, overflow,
        {"README.md": b"# Gallery images\n\nOverflow paper-figure images served by the gallery. See the main branch for attribution and the image policy.\n"},
        f"Stage {len(overflow):,} gallery images",
    )
    prefix = f"https://raw.githubusercontent.com/{repo}/{assets}/"
    for row in rows:
        relative = Path(row["image"]).as_posix()
        row["image"] = prefix + quote(relative, safe="/") if relative in overflow else relative
    manifest = ("window.GALLERY_ADDITIONS = " + json.dumps(rows, ensure_ascii=True) + ";\n").encode()

    for name in VERSIONED_FILES:
        contents = manifest if name == ADDITIONS else git("show", f"HEAD:{name}")
        version = hashlib.sha256(contents).hexdigest()[:12]
        plain = ('"' + name + '"').encode()
        versioned = f'"{name}?v={version}"'.encode()
        if index.count(plain) != 1:
            raise ValueError(f"Expected one resource reference in index.html: {name}")
        index = index.replace(plain, versioned)

    site, site_bytes = stage(PAGES_BRANCH, base, local, {
        "index.html": index,
        ADDITIONS: manifest,
        ".nojekyll": b"",
    }, f"Publish {len(curated) + len(rows):,} paper figures")
    if site_bytes > PAGE_BUDGET:
        raise ValueError("Staged website exceeds the Pages size budget")
    return {
        "pages": site, "assets": assets, "curated": len(curated), "added": len(rows),
        "total": len(curated) + len(rows), "pages_bytes": site_bytes, "asset_bytes": asset_bytes,
        "pages_images": len(local), "overflow_images": len(overflow),
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="GitHub owner/repository for image URLs")
    parser.add_argument("--snapshot", type=Path, help="Local JSON array of reviewed figures to publish")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("--repository needs a GitHub owner and repository name")
    report = build(args.repository, args.snapshot)
    (CACHE / "publication.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
