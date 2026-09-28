#!/usr/bin/env python3
"""Verify that a production artifact matches its allowlist and is self-contained."""

from __future__ import annotations

import posixpath
import re
import stat
import sys
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


REFERENCE_ATTRIBUTES = {"action", "href", "poster", "src"}
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
LEGACY_ALIAS_PATHS = {
    "use-cases/dentsu-media.html",
    "use-cases/kpn-proposals.html",
    "use-cases/lumen-sales.html",
    "use-cases/microsoft-campaigns.html",
    "use-cases/morgan-stanley-knowledge.html",
    "use-cases/oscar-claims.html",
    "use-cases/retailer-invoices.html",
    "use-cases/thyssenkrupp-engineering.html",
}


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.identifiers: set[str] = set()
        self.duplicate_identifiers: set[str] = set()
        self.has_meta_refresh = False
        self.has_html_doctype = False
        self.html_count = 0
        self.head_count = 0
        self.body_count = 0
        self.open_elements: list[str] = []
        self.structure_errors: list[str] = []

    def handle_decl(self, decl: str) -> None:
        if decl.strip().lower() == "doctype html":
            self.has_html_doctype = True

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag not in VOID_ELEMENTS:
            self.open_elements.append(tag)

        if tag == "html":
            self.html_count += 1
        elif tag == "head":
            self.head_count += 1
        elif tag == "body":
            self.body_count += 1

        attributes = {name: value for name, value in attrs}
        identifier = attributes.get("id")
        if identifier:
            if identifier in self.identifiers:
                self.duplicate_identifiers.add(identifier)
            self.identifiers.add(identifier)

        if tag == "meta":
            http_equiv = attributes.get("http-equiv")
            if http_equiv and http_equiv.strip().lower() == "refresh":
                self.has_meta_refresh = True

        for name, value in attrs:
            if not value:
                continue
            if name in REFERENCE_ATTRIBUTES:
                self.references.append(value)
            elif name == "srcset":
                self.references.extend(
                    candidate.strip().split()[0]
                    for candidate in value.split(",")
                    if candidate.strip()
                )

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_ELEMENTS:
            self.structure_errors.append(f"void element has closing tag: {tag}")
            return
        if not self.open_elements:
            self.structure_errors.append(f"unexpected closing tag: {tag}")
            return
        expected = self.open_elements[-1]
        if tag != expected:
            self.structure_errors.append(
                f"mismatched closing tag: expected {expected}, found {tag}"
            )
            if tag in self.open_elements:
                while self.open_elements and self.open_elements[-1] != tag:
                    self.open_elements.pop()
                self.open_elements.pop()
            return
        self.open_elements.pop()


def manifest_paths(manifest: Path) -> list[PurePosixPath]:
    paths: list[PurePosixPath] = []
    seen: set[PurePosixPath] = set()

    for line_number, raw_line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), start=1
    ):
        value = raw_line.strip()
        if not value or value.startswith("#"):
            continue

        path = PurePosixPath(value)
        if path.is_absolute() or value != posixpath.normpath(value) or ".." in path.parts:
            raise ValueError(f"unsafe manifest path on line {line_number}: {value}")
        if path in seen:
            raise ValueError(f"duplicate manifest path on line {line_number}: {value}")

        seen.add(path)
        paths.append(path)

    if not paths:
        raise ValueError("manifest does not contain any files")
    return paths


def is_forbidden(path: PurePosixPath) -> bool:
    return (
        ".git" in path.parts
        or path.as_posix() in LEGACY_ALIAS_PATHS
        or path.name in {".gitignore", "README.md", "navy.html", "privacy-navy.html"}
        or path.name.startswith("preview-")
        or path.parts[0] == "blog-navy"
        or path.name
        in {
            "comparison.css",
            "motion-options.css",
            "motion-options.js",
            "shape-options.css",
            "shape-options.js",
        }
    )


def local_target(artifact: Path, source: Path, reference: str) -> Path | None:
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc:
        return None
    if not parsed.path:
        return source if parsed.fragment else None

    decoded_path = unquote(parsed.path)
    if decoded_path.startswith("/"):
        target = artifact / decoded_path.lstrip("/")
    else:
        target = source.parent / decoded_path

    target = target.resolve()
    try:
        target.relative_to(artifact)
    except ValueError as error:
        raise ValueError(f"reference escapes the artifact: {reference}") from error

    if decoded_path.endswith("/"):
        target /= "index.html"
    return target


def parse_page(path: Path) -> ReferenceParser:
    parser = ReferenceParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def css_references(path: Path) -> list[str]:
    return [match.group(2) for match in CSS_URL.finditer(path.read_text(encoding="utf-8"))]


def verify_permissions(artifact: Path, errors: list[str]) -> None:
    for path in [artifact, *sorted(artifact.rglob("*"))]:
        relative_path = "." if path == artifact else path.relative_to(artifact).as_posix()
        try:
            mode = path.stat().st_mode
        except OSError as error:
            errors.append(f"{relative_path}: cannot inspect permissions: {error}")
            continue

        permissions = stat.S_IMODE(mode)
        if stat.S_ISDIR(mode) and permissions != 0o755:
            errors.append(
                f"{relative_path}: directory mode must be 0755, found {permissions:04o}"
            )
        elif stat.S_ISREG(mode) and permissions != 0o644:
            errors.append(
                f"{relative_path}: file mode must be 0644, found {permissions:04o}"
            )


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: verify-public.py ARTIFACT MANIFEST", file=sys.stderr)
        return 2

    artifact = Path(sys.argv[1]).resolve()
    manifest = Path(sys.argv[2]).resolve()
    errors: list[str] = []

    try:
        expected = manifest_paths(manifest)
    except (OSError, ValueError) as error:
        print(f"Manifest error: {error}", file=sys.stderr)
        return 1

    actual = {
        PurePosixPath(path.relative_to(artifact).as_posix())
        for path in artifact.rglob("*")
        if path.is_file()
    }
    expected_set = set(expected)
    parsed_pages: dict[PurePosixPath, ReferenceParser] = {}

    verify_permissions(artifact, errors)

    for path in sorted(expected_set - actual):
        errors.append(f"missing allowlisted file: {path}")
    for path in sorted(actual - expected_set):
        errors.append(f"unexpected file: {path}")
    for path in sorted(actual):
        if is_forbidden(path):
            errors.append(f"forbidden public file: {path}")

    for relative_path in sorted(actual):
        if relative_path.suffix.lower() not in {".html", ".htm"}:
            continue
        source = artifact / relative_path
        try:
            page = parse_page(source)
        except (OSError, UnicodeError) as error:
            errors.append(f"{relative_path}: cannot parse HTML: {error}")
            continue
        parsed_pages[relative_path] = page
        if not page.has_html_doctype:
            errors.append(f"{relative_path}: missing HTML5 doctype")
        for element, count in (
            ("html", page.html_count),
            ("head", page.head_count),
            ("body", page.body_count),
        ):
            if count != 1:
                errors.append(
                    f"{relative_path}: expected one {element} element, found {count}"
                )
        for identifier in sorted(page.duplicate_identifiers):
            errors.append(f"{relative_path}: duplicate id: {identifier}")
        for structure_error in page.structure_errors:
            errors.append(f"{relative_path}: {structure_error}")
        if page.open_elements:
            errors.append(
                f"{relative_path}: unclosed elements: {', '.join(page.open_elements)}"
            )

    for relative_path in sorted(actual):
        source = artifact / relative_path
        if source.suffix.lower() in {".html", ".htm"}:
            page = parsed_pages.get(relative_path)
            if page is None:
                continue
            references = page.references
            if page.has_meta_refresh:
                errors.append(f"{relative_path}: meta-refresh redirects are forbidden")
        elif source.suffix.lower() == ".css":
            references = css_references(source)
        else:
            continue

        for reference in references:
            try:
                target = local_target(artifact, source, reference)
            except ValueError as error:
                errors.append(f"{relative_path}: {error}")
                continue
            if target is not None and not target.is_file():
                errors.append(f"{relative_path}: missing local reference: {reference}")
            elif target is not None and target.suffix.lower() in {".html", ".htm"}:
                parsed_reference = urlsplit(reference)
                reference_path = unquote(parsed_reference.path)
                if reference_path and not reference_path.lower().endswith(".html"):
                    errors.append(
                        f"{relative_path}: non-canonical local page reference: {reference}"
                    )
                fragment = unquote(parsed_reference.fragment)
                if fragment:
                    target_relative = PurePosixPath(
                        target.relative_to(artifact).as_posix()
                    )
                    target_page = parsed_pages.get(target_relative)
                    if target_page is not None and fragment not in target_page.identifiers:
                        errors.append(
                            f"{relative_path}: missing fragment in {target_relative}: "
                            f"#{fragment}"
                        )

    if errors:
        print("Public artifact verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"Verified {len(actual)} files; HTML structure, IDs, fragments, and all local "
        "references are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
