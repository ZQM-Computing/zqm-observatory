#!/usr/bin/env python3
"""Validate the Observatory's dated data-product bundles using only the stdlib.

This is a structural gate. It does not verify factual accuracy, source contents,
license compatibility, privacy properties of the payload, or field conditions.
Those still require documented human review.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PRODUCT_DIR = re.compile(r"^(\d{4}-\d{2}-\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$")
PRODUCT_REQUIRED = {
    "schema_version", "product_id", "title", "publication_date",
    "geographic_scope", "summary", "license", "source_ids",
    "data_files", "field_verification", "privacy_review",
}
SOURCE_REQUIRED = {"id", "title", "publisher", "url", "retrieval_date", "license", "supports"}


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def read_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{path}: cannot read valid JSON ({exc})")
        return None


def safe_relative_file(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    # A drive-prefixed path is not portable: on POSIX it can look relative,
    # while Windows interprets it as a drive path (absolute or drive-relative).
    if re.match(r"^[A-Za-z]:", value):
        return False
    candidate = Path(value)
    # Require portable, canonical relative paths; reject empty/dot segments,
    # absolute paths, traversal, and control characters.
    parts = value.split("/")
    return (
        not candidate.is_absolute()
        and all(part not in {"", ".", ".."} for part in parts)
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
    )


def is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validate_product(path: Path) -> list[str]:
    errors: list[str] = []
    folder = path.name
    match = PRODUCT_DIR.fullmatch(folder)
    if not match:
        errors.append(f"{path}: directory must be named YYYY-MM-DD-lowercase-slug")
    if path.is_symlink():
        return [f"{path}: product directory must not be a symlink"]
    if not path.is_dir():
        return [f"{path}: product path must be a directory"]
    # A bundle is an untrusted publication boundary. Reject links anywhere in
    # it before reading metadata or method files, not just declared data assets.
    linked_paths = sorted(item for item in path.rglob("*") if item.is_symlink())
    if linked_paths:
        return [f"{item}: symlinks are not allowed inside product bundles" for item in linked_paths]
    product = read_json(path / "product.json", errors)
    sources = read_json(path / "sources.json", errors)
    if not isinstance(product, dict) or not isinstance(sources, list):
        return errors

    missing = sorted(PRODUCT_REQUIRED - product.keys())
    if missing:
        errors.append(f"{path}/product.json: missing fields: {', '.join(missing)}")
    if type(product.get("schema_version")) is not int or product.get("schema_version") != 1:
        errors.append(f"{path}/product.json: schema_version must be integer 1 (booleans are not valid versions)")
    if product.get("product_id") != folder:
        errors.append(f"{path}/product.json: product_id must equal directory name")
    if not is_iso_date(product.get("publication_date")):
        errors.append(f"{path}/product.json: publication_date must be YYYY-MM-DD")
    elif match and product["publication_date"] != match.group(1):
        errors.append(f"{path}/product.json: publication_date must match directory date")
    for key in ("title", "geographic_scope", "summary", "license"):
        if not isinstance(product.get(key), str) or not product[key].strip():
            errors.append(f"{path}/product.json: {key} must be a non-empty string")

    data_files = product.get("data_files")
    if not isinstance(data_files, list) or not data_files:
        errors.append(f"{path}/product.json: data_files must be a non-empty list")
        data_files = []
    if all(isinstance(item, str) for item in data_files) and len(data_files) != len(set(data_files)):
        errors.append(f"{path}/product.json: data_files entries must be unique")
    for item in data_files:
        if not safe_relative_file(item):
            errors.append(f"{path}/product.json: unsafe data_files entry: {item!r}")
            continue
        candidate = path / item
        if candidate.is_symlink():
            errors.append(f"{path}/product.json: symlink data files are not allowed: {item}")
            continue
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(path.resolve())
        except (OSError, ValueError):
            errors.append(f"{path}/product.json: data file escapes product directory: {item}")
            continue
        if not candidate.is_file():
            errors.append(f"{path}/product.json: listed data file does not exist: {item}")

    # Every regular file in a product bundle must be declared as a data asset
    # or be one of the three standard metadata/method files. This prevents an
    # unlisted sidecar from bypassing review and publication inventory.
    declared_files = {
        item for item in data_files
        if safe_relative_file(item)
    }
    allowed_files = {"product.json", "sources.json", "method.md"} | declared_files
    for candidate in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = candidate.relative_to(path).as_posix()
        if relative not in allowed_files:
            errors.append(f"{path}: undeclared file in product bundle: {relative}")

    field = product.get("field_verification")
    if not isinstance(field, dict) or field.get("status") not in {"verified", "not_verified", "not_applicable"} or not isinstance(field.get("notes"), str) or not field["notes"].strip():
        errors.append(f"{path}/product.json: field_verification needs status and explanatory notes")

    privacy = product.get("privacy_review")
    if not isinstance(privacy, dict):
        errors.append(f"{path}/product.json: privacy_review must be an object")
    else:
        if privacy.get("reviewed") is not True:
            errors.append(f"{path}/product.json: privacy_review.reviewed must be true")
        if privacy.get("individual_level_data") is not False:
            errors.append(f"{path}/product.json: individual_level_data must be false")
        if privacy.get("personal_data") is not False:
            errors.append(f"{path}/product.json: personal_data must be false")
        if privacy.get("children_identifiable_data") is not False:
            errors.append(f"{path}/product.json: children_identifiable_data must be false")
        if not isinstance(privacy.get("reviewed_by"), str) or not privacy["reviewed_by"].strip():
            errors.append(f"{path}/product.json: privacy_review.reviewed_by must be a non-empty string")
        review_date = privacy.get("review_date")
        if not is_iso_date(review_date):
            errors.append(f"{path}/product.json: privacy_review.review_date must be YYYY-MM-DD")
        elif is_iso_date(product.get("publication_date")) and review_date > product["publication_date"]:
            errors.append(f"{path}/product.json: privacy_review.review_date must not be after product publication_date")

    if not sources:
        errors.append(f"{path}/sources.json: at least one source is required")
    source_ids: list[str] = []
    for index, source in enumerate(sources):
        label = f"{path}/sources.json entry {index + 1}"
        if not isinstance(source, dict):
            errors.append(f"{label}: must be an object")
            continue
        absent = sorted(SOURCE_REQUIRED - source.keys())
        if absent:
            errors.append(f"{label}: missing fields: {', '.join(absent)}")
        sid = source.get("id")
        if not isinstance(sid, str) or not sid.strip():
            errors.append(f"{label}: id must be a non-empty string")
        else:
            source_ids.append(sid)
        for key in ("title", "publisher", "license"):
            if not isinstance(source.get(key), str) or not source[key].strip():
                errors.append(f"{label}: {key} must be a non-empty string")
        url = source.get("url")
        valid_url = False
        if isinstance(url, str):
            try:
                parsed_url = urlparse(url)
                # Accessing hostname/port also validates malformed IPv6 and
                # port syntax; keep all parser-dependent work in this guard.
                hostname = parsed_url.hostname
                port = parsed_url.port
                valid_url = (
                    parsed_url.scheme == "https"
                    and bool(hostname)
                    and parsed_url.username is None
                    and parsed_url.password is None
                    and not any(ch.isspace() for ch in url)
                    and (port is None or 1 <= port <= 65535)
                    and not any(ord(ch) < 32 or ord(ch) == 127 for ch in url)
                )
            except ValueError:
                valid_url = False
        if not valid_url:
            errors.append(f"{label}: url must be a valid HTTPS URL with a hostname, valid port, and no embedded credentials")
        retrieval_date = source.get("retrieval_date")
        if not is_iso_date(retrieval_date):
            errors.append(f"{label}: retrieval_date must be YYYY-MM-DD")
        elif is_iso_date(product.get("publication_date")) and retrieval_date > product["publication_date"]:
            errors.append(f"{label}: retrieval_date must not be after product publication_date")
        if not isinstance(source.get("supports"), list) or not source["supports"] or any(not isinstance(x, str) or not x.strip() for x in source["supports"]):
            errors.append(f"{label}: supports must list the claims this source supports")

    if len(source_ids) != len(set(source_ids)):
        errors.append(f"{path}/sources.json: source IDs must be unique")
    declared_ids = product.get("source_ids")
    if not isinstance(declared_ids, list) or not declared_ids or any(not isinstance(x, str) or not x.strip() for x in declared_ids):
        errors.append(f"{path}/product.json: source_ids must be a non-empty list of non-empty strings")
    else:
        if len(declared_ids) != len(set(declared_ids)):
            errors.append(f"{path}/product.json: source_ids must be unique")
        if set(declared_ids) != set(source_ids):
            errors.append(f"{path}: product source_ids must match sources.json IDs")
    if not (path / "method.md").is_file():
        errors.append(f"{path}: method.md is required")
    else:
        try:
            method_text = (path / "method.md").read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path}/method.md: cannot read UTF-8 method text ({exc})")
        else:
            if len(method_text.strip()) < 100:
                errors.append(f"{path}/method.md: method must explain reproducible steps (at least 100 characters)")
    return errors


def validate_data_dir(data_dir: Path) -> list[str]:
    if data_dir.is_symlink():
        return [f"{data_dir}: data directory must not be a symlink"]
    if not data_dir.is_dir():
        return [f"{data_dir}: data directory does not exist or is not a directory"]
    errors: list[str] = []
    products: list[Path] = []
    for entry in sorted(data_dir.iterdir()):
        # Hidden repository/editor sentinels are not product payloads. Every
        # visible top-level entry, however, must be a real product directory;
        # otherwise files can sit beside reviewed bundles without being gated.
        if entry.name.startswith("."):
            continue
        if entry.is_symlink():
            errors.append(f"{entry}: top-level data entries must not be symlinks")
        elif entry.is_dir():
            products.append(entry)
        else:
            errors.append(
                f"{entry}: unexpected top-level file; data/ must contain dated product directories only"
            )

    for product_dir in products:
        errors.extend(validate_product(product_dir))
    if not products:
        print("No data-product bundles found; structural validation is ready for the first product.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="directory containing dated product bundles")
    args = parser.parse_args()
    errors = validate_data_dir(args.data_dir)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        print(f"Product validation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    print("Product bundle structure passed. Human factual, privacy, license, and field verification remain required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
