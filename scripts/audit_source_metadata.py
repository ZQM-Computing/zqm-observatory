#!/usr/bin/env python3
"""Capture bounded ArcGIS layer metadata only; never request feature records.

This preflight does not authorize collection or publication. It requests only
FeatureServer/<layer-id>?f=pjson metadata from the allowlisted County host.
Non-layer sources are recorded as skipped and are never fetched by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_REGISTER = Path("config/source-rights.json")
ALLOWED_HOSTS = {"maps5.vcgov.org"}
MAX_RESPONSE_BYTES = 2_000_000
TIMEOUT_SECONDS = 15
USER_AGENT = "ZQM-Observatory-Metadata-Preflight/1.0 (+https://github.com/ZQM-Computing/zqm-observatory)"


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def layer_metadata_url(value: Any, expected_layer_id: Any = None) -> tuple[str | None, str | None]:
    """Return a normalized metadata-only URL, or a reason to skip/refuse it."""
    if not isinstance(value, str):
        return None, "service_url is not a string"
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return None, "malformed URL or port"
    expected_prefix = "/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/"
    if not parsed.path.startswith(expected_prefix) or not parsed.path[len(expected_prefix):].isdigit():
        return None, "not an allowlisted ArcGIS layer URL; skipped without network request"
    path_layer_id = int(parsed.path[len(expected_prefix):])
    if expected_layer_id is not None and (not isinstance(expected_layer_id, int) or isinstance(expected_layer_id, bool) or path_layer_id != expected_layer_id):
        return None, "registered layer_id does not match the layer URL; refusing network request"
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        return None, "host or scheme is outside the metadata preflight allowlist"
    if parsed.username is not None or parsed.password is not None or port not in (None, 443):
        return None, "credentials or non-standard port are not allowed"
    if parsed.query or parsed.fragment:
        return None, "query strings and fragments are not allowed in registered service URLs"
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", urlencode({"f": "pjson"}), "")), None


def summarize_metadata(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("response JSON root is not an object")
    if "error" in payload:
        raise ValueError("ArcGIS returned an error object")
    # A metadata endpoint returning feature payloads is unexpected and must fail closed.
    if "features" in payload:
        raise ValueError("response unexpectedly contains feature records; refusing to treat it as metadata")
    if not isinstance(payload.get("id"), int) or not isinstance(payload.get("name"), str) or not payload["name"].strip():
        raise ValueError("response lacks a valid layer id or name")
    fields = payload.get("fields", [])
    if not isinstance(fields, list) or any(not isinstance(field, dict) or not isinstance(field.get("name"), str) for field in fields):
        raise ValueError("metadata fields member must be an array of named field objects")
    return {
        "layer_id": payload.get("id"),
        "name": payload.get("name"),
        "type": payload.get("type"),
        "geometry_type": payload.get("geometryType"),
        "description": payload.get("description"),
        "copyright_text": payload.get("copyrightText"),
        "max_record_count": payload.get("maxRecordCount"),
        "capabilities": payload.get("capabilities"),
        "object_id_field": payload.get("objectIdField"),
        "global_id_field": payload.get("globalIdField"),
        "spatial_reference": payload.get("extent", {}).get("spatialReference")
        if isinstance(payload.get("extent"), dict) else payload.get("spatialReference"),
        "field_count": len(fields),
        "fields": [
            {
                "name": field.get("name"),
                "type": field.get("type"),
                "alias": field.get("alias"),
                "nullable": field.get("nullable"),
                "domain": field.get("domain"),
            }
            for field in fields
            if isinstance(field, dict)
        ],
    }


def capture_one(source: dict[str, Any], opener=None) -> dict[str, Any]:
    source_id = source.get("id")
    result: dict[str, Any] = {
        "source_id": source_id,
        "title": source.get("title"),
        "rights_decision": source.get("decision"),
        "request_scope": "layer metadata only; no feature query",
        "metadata_url": None,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SKIPPED",
    }
    url, reason = layer_metadata_url(source.get("service_url"), source.get("layer_id"))
    if reason:
        result["reason"] = reason
        return result
    result["metadata_url"] = url
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    opener = opener or build_opener(NoRedirectHandler())
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        result["http_status"] = status
        result["content_type"] = content_type
        if status != 200:
            result.update(status="ERROR", reason=f"unexpected HTTP status {status}")
            return result
        if len(raw) > MAX_RESPONSE_BYTES:
            result.update(status="ERROR", reason=f"response exceeds {MAX_RESPONSE_BYTES} byte limit")
            return result
        if "json" not in content_type.lower():
            result.update(status="ERROR", reason="response content type is not JSON")
            return result
        result["response_bytes"] = len(raw)
        result["response_sha256"] = hashlib.sha256(raw).hexdigest()
        try:
            payload = json.loads(raw.decode("utf-8"))
            metadata = summarize_metadata(payload)
            expected_layer_id = source.get("layer_id")
            if expected_layer_id is not None and metadata["layer_id"] != expected_layer_id:
                raise ValueError("response layer id does not match registered layer id")
            result["metadata"] = metadata
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            result.update(status="ERROR", reason=f"invalid layer metadata: {exc}")
            return result
        result["status"] = "OK"
        if source.get("decision") not in {"APPROVED", "APPROVED_WITH_CONDITIONS", "INTERNAL_ONLY"}:
            result["collection_gate"] = "BLOCKED_BY_REGISTER_DECISION"
        else:
            result["collection_gate"] = "REVIEW_REGISTER_AND_SEPARATE_PRODUCT_GATES"
        return result
    except HTTPError as exc:
        result.update(status="ERROR", http_status=exc.code, reason=f"HTTP error {exc.code}")
    except (URLError, TimeoutError, OSError) as exc:
        result.update(status="ERROR", reason=f"request failed: {exc}")
    return result


def build_report(register: Any, opener=None) -> dict[str, Any]:
    if not isinstance(register, dict) or not isinstance(register.get("sources"), list):
        raise ValueError("register must be an object containing a sources array")
    records = [
        capture_one(source, opener=opener) if isinstance(source, dict) else {
            "status": "ERROR", "reason": "source entry is not an object"
        }
        for source in register["sources"]
    ]
    return {
        "schema_version": 1,
        "report_type": "arcgis-layer-metadata-preflight",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "safety_scope": {
            "feature_records_requested": False,
            "bulk_download_performed": False,
            "rights_approval_granted": False,
            "note": "Metadata presence does not establish reuse rights, data quality, currentness, or publication eligibility."
        },
        "counts": {
            "total": len(records),
            "ok": sum(r.get("status") == "OK" for r in records),
            "skipped": sum(r.get("status") == "SKIPPED" for r in records),
            "errors": sum(r.get("status") == "ERROR" for r in records),
            "blocked_by_rights_register": sum(r.get("collection_gate") == "BLOCKED_BY_REGISTER_DECISION" for r in records),
        },
        "sources": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path; stdout if omitted.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero if any eligible metadata request fails.")
    args = parser.parse_args()
    try:
        register = json.loads(args.register.read_text(encoding="utf-8"))
        report = build_report(register)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: cannot build metadata preflight: {exc}", file=sys.stderr)
        return 2
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    try:
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding="utf-8")
        else:
            print(serialized, end="")
    except OSError as exc:
        print(f"ERROR: cannot write report: {exc}", file=sys.stderr)
        return 2
    print(f"Metadata preflight: {report['counts']['ok']} OK, {report['counts']['skipped']} skipped, {report['counts']['errors']} errors; no feature records requested.", file=sys.stderr)
    return 1 if args.strict and report["counts"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
