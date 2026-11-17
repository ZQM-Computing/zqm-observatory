#!/usr/bin/env python3
"""Create and verify Ed25519 attestations for independently verified evidence bundles."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.strict_json import loads_strict
except ModuleNotFoundError:
    from strict_json import loads_strict

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
except ImportError:  # fail closed with an actionable CLI error
    serialization = None
    Ed25519PrivateKey = Ed25519PublicKey = None

try:
    from scripts.verify_release_evidence import verify_manifest
except ModuleNotFoundError:
    from verify_release_evidence import verify_manifest


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public_key_id(public_key: Any) -> str:
    raw = public_key.public_bytes(encoding=serialization.Encoding.DER, format=serialization.PublicFormat.SubjectPublicKeyInfo)
    return "ed25519-sha256:" + sha256_bytes(raw)


def load_json(path: Path) -> dict[str, Any]:
    value = loads_strict(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def build_payload(manifest_path: Path, key_id: str, issuer: str) -> dict[str, Any]:
    errors = verify_manifest(manifest_path)
    if errors:
        raise ValueError("evidence bundle verification failed: " + "; ".join(errors))
    manifest = load_json(manifest_path)
    artifacts = manifest["artifacts"]
    policy = artifacts["release_policy"]["sha256"]
    reviews = artifacts["human_reviews"]["sha256"]
    return {
        "schema_version": 1,
        "attestation_type": "zqm_observatory_release_evidence_signature",
        "algorithm": "Ed25519",
        "key_id": key_id,
        "issuer": issuer,
        "issued_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "manifest_file": manifest_path.name,
        "manifest_sha256": sha256_bytes(manifest_path.read_bytes()),
        "decision": manifest["decision"],
        "publication_authorized_by_manifest": manifest.get("publication_authorized_by_manifest"),
        "policy_sha256": policy,
        "human_reviews_sha256": reviews,
        "artifacts": {role: item["sha256"] for role, item in sorted(artifacts.items())},
        "meaning": "Signature authenticates this payload and its referenced bytes; it does not grant publication authorization.",
    }


def sign(manifest_path: Path, private_key_path: Path, output_path: Path, issuer: str, expected_key_id: str | None) -> None:
    if Ed25519PrivateKey is None:
        raise RuntimeError("Ed25519 support requires the 'cryptography' package; install requirements-security.txt")
    key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("private key must be an unencrypted PEM Ed25519 private key")
    key_id = public_key_id(key.public_key())
    if expected_key_id and expected_key_id != key_id:
        raise ValueError("--key-id does not match the private key fingerprint")
    payload = build_payload(manifest_path, key_id, issuer)
    envelope = {
        "schema_version": 1,
        "envelope_type": "zqm_observatory_ed25519_attestation",
        "payload": payload,
        "signature_base64": base64.b64encode(key.sign(canonical_json(payload))).decode("ascii"),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n")
    print(f"Signed evidence manifest SHA-256 {payload['manifest_sha256']} with key {key_id}. Signature does not authorize publication.")


def verify(attestation_path: Path, public_key_path: Path, manifest_path: Path) -> list[str]:
    errors: list[str] = []
    if Ed25519PublicKey is None:
        return ["Ed25519 support requires the 'cryptography' package; install requirements-security.txt"]
    try:
        key = serialization.load_pem_public_key(public_key_path.read_bytes())
        envelope = load_json(attestation_path)
        manifest = load_json(manifest_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return [f"cannot load attestation, public key, or manifest: {exc}"]
    if not isinstance(key, Ed25519PublicKey):
        return ["trusted public key must be PEM Ed25519"]
    payload = envelope.get("payload")
    if envelope.get("envelope_type") != "zqm_observatory_ed25519_attestation" or type(envelope.get("schema_version")) is not int or envelope.get("schema_version") != 1 or not isinstance(payload, dict):
        return ["attestation envelope schema is invalid"]
    required_payload_fields = {
        "schema_version", "attestation_type", "algorithm", "key_id", "issuer",
        "issued_at", "manifest_file", "manifest_sha256", "decision",
        "publication_authorized_by_manifest", "policy_sha256",
        "human_reviews_sha256", "artifacts", "meaning",
    }
    if set(payload) != required_payload_fields:
        errors.append("attestation payload fields do not match the required schema")
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
        errors.append("attestation payload schema_version must be integer 1")
    if payload.get("attestation_type") != "zqm_observatory_release_evidence_signature":
        errors.append("attestation payload type is invalid")
    if payload.get("algorithm") != "Ed25519":
        errors.append("attestation payload algorithm is invalid")
    issuer = payload.get("issuer")
    if not isinstance(issuer, str) or not issuer.strip():
        errors.append("attestation issuer must be a non-empty string")
    issued_at = payload.get("issued_at")
    if not isinstance(issued_at, str):
        errors.append("attestation issued_at must be a timezone-aware ISO-8601 timestamp")
    else:
        try:
            parsed_issued_at = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
            if parsed_issued_at.tzinfo is None or parsed_issued_at.utcoffset() is None:
                errors.append("attestation issued_at must include a timezone")
        except ValueError:
            errors.append("attestation issued_at must be a valid ISO-8601 timestamp")
    if payload.get("manifest_file") != manifest_path.name:
        errors.append("attestation manifest_file does not match the supplied manifest")
    if not isinstance(payload.get("meaning"), str) or not payload.get("meaning", "").strip():
        errors.append("attestation meaning must be a non-empty string")
    actual_key_id = public_key_id(key)
    if payload.get("key_id") != actual_key_id:
        errors.append("attestation key_id does not match trusted public-key fingerprint")
    if payload.get("manifest_sha256") != sha256_bytes(manifest_path.read_bytes()):
        errors.append("manifest SHA-256 does not match signed payload")
    if payload.get("decision") != manifest.get("decision") or payload.get("publication_authorized_by_manifest") is not False:
        errors.append("signed decision/authorization fields do not match the non-authorizing manifest")
    artifacts = manifest.get("artifacts")
    expected_artifacts = {role: item.get("sha256") for role, item in sorted(artifacts.items())} if isinstance(artifacts, dict) else None
    if payload.get("artifacts") != expected_artifacts:
        errors.append("signed artifact hashes do not match manifest")
    if not isinstance(artifacts, dict) or payload.get("policy_sha256") != artifacts.get("release_policy", {}).get("sha256") or payload.get("human_reviews_sha256") != artifacts.get("human_reviews", {}).get("sha256"):
        errors.append("signed policy/review hashes do not match manifest")
    try:
        signature = base64.b64decode(envelope.get("signature_base64", ""), validate=True)
        key.verify(signature, canonical_json(payload))
    except Exception:
        errors.append("Ed25519 signature verification failed")
    if not errors:
        errors.extend(verify_manifest(manifest_path))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sign_parser = sub.add_parser("sign", help="sign an independently verified evidence manifest")
    sign_parser.add_argument("--manifest", required=True, type=Path)
    sign_parser.add_argument("--private-key", required=True, type=Path)
    sign_parser.add_argument("--output", required=True, type=Path)
    sign_parser.add_argument("--issuer", required=True)
    sign_parser.add_argument("--key-id")
    verify_parser = sub.add_parser("verify", help="verify signature against an explicitly trusted public key")
    verify_parser.add_argument("--attestation", required=True, type=Path)
    verify_parser.add_argument("--public-key", required=True, type=Path)
    verify_parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "sign":
            sign(args.manifest, args.private_key, args.output, args.issuer, args.key_id)
        else:
            errors = verify(args.attestation, args.public_key, args.manifest)
            if errors:
                print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
                return 1
            print("Attestation signature and evidence bundle verified; publication authorization is not granted.")
    except (OSError, ValueError, RuntimeError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
