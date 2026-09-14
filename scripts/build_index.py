#!/usr/bin/env python3
"""Build a static PEP 503 index from ascend-catlass/actions releases."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path


SOURCE_REPOSITORY = "ascend-catlass/actions"
PACKAGE_NAME = "ascend-catlass-dsl"
NORMALIZED_PACKAGE_NAME = "ascend-catlass-dsl"
WHEEL_PREFIX = "ascend_catlass_dsl-"
SHA256_RE = re.compile(r"^sha256:([0-9a-f]{64})$")


@dataclass(frozen=True)
class Wheel:
    name: str
    url: str
    sha256: str


def fetch_releases(repository: str = SOURCE_REPOSITORY) -> list[dict]:
    releases: list[dict] = []
    page = 1
    token = os.environ.get("GITHUB_TOKEN", "")
    while True:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ascend-catlass-pypi-index",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repository}/releases?per_page=100&page={page}",
            headers=headers,
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.load(response)
        if not isinstance(batch, list):
            raise RuntimeError("GitHub releases API did not return a list")
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def collect_wheels(releases: list[dict]) -> list[Wheel]:
    wheels: dict[str, tuple[tuple[str, int], Wheel]] = {}
    for release in releases:
        if release.get("draft"):
            continue
        release_order = (
            release.get("published_at") or release.get("created_at") or "",
            release.get("id") or 0,
        )
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if not (name.startswith(WHEEL_PREFIX) and name.endswith(".whl")):
                continue

            digest_match = SHA256_RE.fullmatch(asset.get("digest") or "")
            if digest_match is None:
                raise RuntimeError(f"Wheel asset has no valid SHA256 digest: {name}")
            wheel = Wheel(
                name=name,
                url=asset["browser_download_url"],
                sha256=digest_match.group(1),
            )
            previous = wheels.get(name)
            if previous is None or release_order > previous[0]:
                wheels[name] = (release_order, wheel)
            elif release_order == previous[0] and previous[1] != wheel:
                raise RuntimeError(
                    f"Conflicting release assets have the same publication order: {name}"
                )

    if not wheels:
        raise RuntimeError(f"No {PACKAGE_NAME} wheels found in {SOURCE_REPOSITORY} releases")
    return sorted(
        (wheel for _, wheel in wheels.values()),
        key=lambda wheel: wheel.name,
        reverse=True,
    )


def write_site(output: Path, wheels: list[Wheel]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / ".nojekyll").touch()

    project_dir = output / "simple" / NORMALIZED_PACKAGE_NAME
    project_dir.mkdir(parents=True, exist_ok=True)

    root_page = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Ascend CATLASS Package Index</title></head>
<body>
  <h1>Ascend CATLASS Package Index</h1>
  <p>This is a supplemental Python package index backed by verified GitHub Release assets.</p>
  <pre><code>python -m pip install --pre --extra-index-url https://ascend-catlass.github.io/simple/ ascend-catlass-dsl</code></pre>
  <p><a href="simple/">Browse the Simple API</a></p>
</body>
</html>
"""
    (output / "index.html").write_text(root_page, encoding="utf-8")

    simple_root = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="pypi:repository-version" content="1.4">
  <title>Simple index</title>
</head>
<body>
  <a href="{NORMALIZED_PACKAGE_NAME}/">{PACKAGE_NAME}</a>
</body>
</html>
"""
    (output / "simple" / "index.html").write_text(simple_root, encoding="utf-8")

    links = []
    for wheel in wheels:
        href = f"{wheel.url}#sha256={wheel.sha256}"
        links.append(
            "  <a href=\"{}\" data-requires-python=\"&gt;=3.10,&lt;3.14\">{}</a><br>".format(
                html.escape(href, quote=True), html.escape(wheel.name)
            )
        )
    project_page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="pypi:repository-version" content="1.4">
  <title>{package} files</title>
</head>
<body>
{links}
</body>
</html>
""".format(package=PACKAGE_NAME, links="\n".join(links))
    (project_dir / "index.html").write_text(project_page, encoding="utf-8")

    manifest = {
        "source_repository": SOURCE_REPOSITORY,
        "package": PACKAGE_NAME,
        "files": [wheel.__dict__ for wheel in wheels],
        "content_sha256": hashlib.sha256(project_page.encode()).hexdigest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--releases-json",
        type=Path,
        help="Use a local GitHub releases API response instead of the network",
    )
    args = parser.parse_args()

    if args.releases_json:
        releases = json.loads(args.releases_json.read_text(encoding="utf-8"))
    else:
        releases = fetch_releases()
    wheels = collect_wheels(releases)
    write_site(args.output, wheels)
    print(f"Published {len(wheels)} wheels for {PACKAGE_NAME}")


if __name__ == "__main__":
    main()
