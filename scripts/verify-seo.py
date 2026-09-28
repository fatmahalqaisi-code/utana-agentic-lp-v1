#!/usr/bin/env python3
"""Verify canonical, social, favicon, robots, and sitemap metadata."""

from __future__ import annotations

import struct
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath


ORIGIN = "https://utana.agentic.technologies"
SOCIAL_IMAGE_URL = f"{ORIGIN}/assets/social/utana-social-preview.png"
HOME_PATH = PurePosixPath("index.html")
HOME_SOCIAL_IMAGE_URL = (
    "https://utana-agentic-lp-v.vercel.app/assets/social/utana-social-preview.png"
)
HOME_SOCIAL_TITLE = "Utana — Agentic Workflow Automation"
HOME_SOCIAL_DESCRIPTION = (
    "AI agents that automate repetitive workflows and help teams move faster."
)
PRIVACY_PATH = PurePosixPath("privacy.html")
SPECIAL_PUBLIC_PAGES = {PurePosixPath("404.html"): "noindex"}
SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"


class HeadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.in_title = False
        self.title_parts: list[str] = []
        self.metas: dict[str, list[str]] = {}
        self.links: dict[str, list[dict[str, str]]] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = {name.lower(): value or "" for name, value in attrs}
        if tag == "head":
            self.in_head = True
        elif self.in_head and tag == "title":
            self.in_title = True
        elif self.in_head and tag == "meta":
            key = attributes.get("name") or attributes.get("property")
            if key:
                self.metas.setdefault(key.lower(), []).append(attributes.get("content", ""))
        elif self.in_head and tag == "link":
            for relation in attributes.get("rel", "").lower().split():
                self.links.setdefault(relation, []).append(attributes)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "head":
            self.in_head = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()


def manifest_html_paths(manifest: Path) -> list[PurePosixPath]:
    paths: list[PurePosixPath] = []
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        value = raw_line.strip()
        if value and not value.startswith("#") and value.endswith(".html"):
            paths.append(PurePosixPath(value))
    return paths


def one(values: list[str] | None, label: str, path: PurePosixPath, errors: list[str]) -> str:
    if not values:
        errors.append(f"{path}: missing {label}")
        return ""
    if len(values) != 1:
        errors.append(f"{path}: expected one {label}, found {len(values)}")
    return values[0]


def check_png(path: Path, width: int, height: int, errors: list[str]) -> None:
    try:
        with path.open("rb") as image:
            header = image.read(24)
    except OSError as error:
        errors.append(f"missing image asset {path.name}: {error}")
        return
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        errors.append(f"{path.name}: expected a PNG image")
        return
    actual_width, actual_height = struct.unpack(">II", header[16:24])
    if (actual_width, actual_height) != (width, height):
        errors.append(
            f"{path.name}: expected {width}x{height}, found {actual_width}x{actual_height}"
        )


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: verify-seo.py ARTIFACT MANIFEST", file=sys.stderr)
        return 2

    artifact = Path(sys.argv[1]).resolve()
    manifest = Path(sys.argv[2]).resolve()
    errors: list[str] = []

    try:
        manifest_pages = manifest_html_paths(manifest)
    except OSError as error:
        print(f"SEO verification failed: {error}", file=sys.stderr)
        return 1

    html_paths = [path for path in manifest_pages if path not in SPECIAL_PUBLIC_PAGES]
    if not html_paths:
        errors.append("manifest does not contain canonical HTML pages")

    for relative_path, expected_robots in SPECIAL_PUBLIC_PAGES.items():
        if relative_path not in manifest_pages:
            errors.append(f"manifest is missing special public page {relative_path}")
            continue

        parser = HeadParser()
        try:
            parser.feed((artifact / relative_path).read_text(encoding="utf-8"))
            parser.close()
        except OSError as error:
            errors.append(f"{relative_path}: cannot read page: {error}")
            continue

        if parser.metas.get("robots") != [expected_robots]:
            errors.append(
                f"{relative_path}: special public page robots policy must be "
                f"{expected_robots!r}"
            )

    canonical_urls: set[str] = set()
    for relative_path in html_paths:
        page_path = artifact / relative_path
        parser = HeadParser()
        try:
            parser.feed(page_path.read_text(encoding="utf-8"))
            parser.close()
        except OSError as error:
            errors.append(f"{relative_path}: cannot read page: {error}")
            continue

        expected_url = f"{ORIGIN}/{relative_path.as_posix()}"
        expected_type = (
            "article"
            if relative_path.parts[0] in {"blog", "use-cases"}
            else "website"
        )
        title = parser.title
        if not title:
            errors.append(f"{relative_path}: missing title")
        description = one(
            parser.metas.get("description"), "meta description", relative_path, errors
        )
        canonical = one(
            [link.get("href", "") for link in parser.links.get("canonical", [])],
            "canonical link",
            relative_path,
            errors,
        )
        if canonical != expected_url:
            errors.append(
                f"{relative_path}: canonical must be {expected_url}, found {canonical or '(empty)'}"
            )
        elif canonical in canonical_urls:
            errors.append(f"{relative_path}: duplicate canonical URL {canonical}")
        canonical_urls.add(canonical)

        social_title = HOME_SOCIAL_TITLE if relative_path == HOME_PATH else title
        social_description = (
            HOME_SOCIAL_DESCRIPTION if relative_path == HOME_PATH else description
        )
        social_image = (
            HOME_SOCIAL_IMAGE_URL if relative_path == HOME_PATH else SOCIAL_IMAGE_URL
        )
        expected_meta = {
            "og:title": social_title,
            "og:description": social_description,
            "og:type": expected_type,
            "og:url": expected_url,
            "og:image": social_image,
            "og:image:width": "1200",
            "og:image:height": "630",
            "twitter:card": "summary_large_image",
            "twitter:title": social_title,
            "twitter:description": social_description,
            "twitter:image": social_image,
        }
        if relative_path == HOME_PATH:
            expected_meta.update({"og:site_name": "Utana", "og:image:type": "image/png"})
        for key, expected in expected_meta.items():
            actual = one(parser.metas.get(key), key, relative_path, errors)
            if actual != expected:
                errors.append(
                    f"{relative_path}: {key} must be {expected!r}, found {actual!r}"
                )

        robots = parser.metas.get("robots", [])
        if relative_path == PRIVACY_PATH:
            if robots != ["noindex,follow"]:
                errors.append(
                    f"{relative_path}: privacy robots policy must be 'noindex,follow'"
                )
        elif any("noindex" in value.lower() for value in robots):
            errors.append(f"{relative_path}: canonical indexable page contains noindex")

        icons = parser.links.get("icon", [])
        expected_icons = {
            ("/favicon.svg", "image/svg+xml", ""),
            ("/favicon-32x32.png", "image/png", "32x32"),
        }
        actual_icons = {
            (icon.get("href", ""), icon.get("type", ""), icon.get("sizes", ""))
            for icon in icons
        }
        if actual_icons != expected_icons:
            errors.append(f"{relative_path}: favicon metadata is inconsistent")

        apple_icons = parser.links.get("apple-touch-icon", [])
        if apple_icons != [{"rel": "apple-touch-icon", "href": "/apple-touch-icon.png", "sizes": "180x180"}]:
            errors.append(f"{relative_path}: Apple touch icon metadata is inconsistent")

    sitemap_path = artifact / "sitemap.xml"
    try:
        root = ET.parse(sitemap_path).getroot()
        sitemap_url_list = [
            element.text.strip()
            for element in root.findall(
                f"{{{SITEMAP_NAMESPACE}}}url/{{{SITEMAP_NAMESPACE}}}loc"
            )
            if element.text and element.text.strip()
        ]
        sitemap_urls = set(sitemap_url_list)
        if root.tag != f"{{{SITEMAP_NAMESPACE}}}urlset":
            errors.append("sitemap.xml: invalid sitemap urlset namespace")
        if len(sitemap_url_list) != len(sitemap_urls):
            errors.append("sitemap.xml: duplicate URL entries")
    except (OSError, ET.ParseError) as error:
        errors.append(f"sitemap.xml: cannot parse sitemap: {error}")
        sitemap_urls = set()

    expected_sitemap_urls = {
        f"{ORIGIN}/{path.as_posix()}" for path in html_paths if path != PRIVACY_PATH
    }
    for url in sorted(expected_sitemap_urls - sitemap_urls):
        errors.append(f"sitemap.xml: missing canonical URL {url}")
    for url in sorted(sitemap_urls - expected_sitemap_urls):
        errors.append(f"sitemap.xml: unexpected or non-indexable URL {url}")

    robots_path = artifact / "robots.txt"
    try:
        robots_lines = [
            line.strip()
            for line in robots_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as error:
        errors.append(f"robots.txt: cannot read file: {error}")
        robots_lines = []
    expected_robots = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {ORIGIN}/sitemap.xml",
    ]
    if robots_lines != expected_robots:
        errors.append("robots.txt: directives do not match the production origin")

    check_png(artifact / "assets/social/utana-social-preview.png", 1200, 630, errors)
    check_png(artifact / "favicon-32x32.png", 32, 32, errors)
    check_png(artifact / "apple-touch-icon.png", 180, 180, errors)

    if errors:
        print("SEO verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"Verified SEO metadata for {len(html_paths)} canonical pages and "
        f"{len(expected_sitemap_urls)} sitemap URLs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
