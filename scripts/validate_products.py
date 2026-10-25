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


def read_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: cannot read valid JSON ({exc})")
        return None


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
    product = read_json(path / "product.json", errors)
    sources = read_json(path / "sources.json", errors)
    if not isinstance(product, dict) or not isinstance(sources, list):
        return errors

    missing = sorted(PRODUCT_REQUIRED - product.keys())
    if missing:
        errors.append(f"{path}/product.json: missing fields: {', '.join(missing)}")
    if product.get("schema_version") != 1:
        errors.append(f"{path}/product.json: schema_version must be 1")
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
        if not isinstance(item, str) or not item or Path(item).is_absolute() or ".." in Path(item).parts:
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
        if not is_iso_date(privacy.get("review_date")):
            errors.append(f"{path}/product.json: privacy_review.review_date must be YYYY-MM-DD")

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
        parsed_url = urlparse(url) if isinstance(url, str) else None
        if (
            parsed_url is None
            or parsed_url.scheme != "https"
            or not parsed_url.hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
            or any(ch.isspace() for ch in url)
        ):
            errors.append(f"{label}: url must be a valid HTTPS URL with a hostname and no embedded credentials")
        if not is_iso_date(source.get("retrieval_date")):
            errors.append(f"{label}: retrieval_date must be YYYY-MM-DD")
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
    elif len((path / "method.md").read_text(encoding="utf-8").strip()) < 100:
        errors.append(f"{path}/method.md: method must explain reproducible steps (at least 100 characters)")
    return errors


def validate_data_dir(data_dir: Path) -> list[str]:
    if not data_dir.is_dir():
        return [f"{data_dir}: data directory does not exist"]
    products = sorted(p for p in data_dir.iterdir() if p.is_dir() and not p.name.startswith("."))
    errors: list[str] = []
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
