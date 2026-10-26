# First data product: release gate

This checklist turns the Observatory's existing methods and product-bundle standard into an executable review sequence. It does not authorize collection or publication of any currently blocked source.

## 0. Choose a question before choosing data

- [ ] State one decision-relevant question in plain language.
- [ ] Define the geographic boundary, intended audience, publication date, and expected shelf life.
- [ ] Explain why a new product is useful and what it will not answer.
- [ ] Prefer the smallest product that answers the question; do not expand scope just because a source has more fields.
- [ ] Record the product owner and reviewer.

**Stop if:** the question requires individual-level tracking, personal data, identifiable children's data, private/credentialed sources, or unsupported claims about safety, access, service status, or suitability.

## 1. Clear every source before collection

For each exact dataset or layer:

- [ ] Identify the publisher/steward, stable item ID, exact URL, layer/version, and update cadence.
- [ ] Preserve the authoritative terms/license evidence and its retrieval timestamp.
- [ ] Complete the item-level rights review for the intended operations: access, collection, transformation, joins, public display, and redistribution of raw or derived data.
- [ ] Record required attribution, share-alike conditions, restrictions, and unresolved ambiguity in `config/source-rights.json`.
- [ ] Run `python scripts/validate_source_rights.py` and the unit tests.
- [ ] Confirm the register's approved uses match the proposed product's actual operations.

A public endpoint, a downloadable file, or a metadata response is not a rights approval. Any `null` permission remains unknown. If the planned use is not explicitly permitted, stop or choose another source.

## 2. Capture bounded evidence and preserve provenance

- [ ] Record retrieval timestamp in UTC, source version/date, source URL and stable identifier.
- [ ] Preserve source hashes and metadata snapshots where policy and rights allow.
- [ ] Record software/tool versions, commands, configuration, CRS/SRID, units, and transformation order.
- [ ] Keep source material, normalized intermediates, and publication assets separate.
- [ ] Never overwrite source files; do not commit credentials or unreviewed source captures.
- [ ] Use deterministic synthetic fixtures for pipeline development while real-source rights are unresolved.

## 3. Validate the data and the meaning

- [ ] Check schema, required fields, nulls, duplicate identifiers, geometry type/validity, CRS, units, temporal coverage, and expected geographic extent.
- [ ] Check joins for unexpected row multiplication, dropped records, key mismatch, and CRS mismatch.
- [ ] Compare counts and summary statistics before and after each transformation.
- [ ] Distinguish source-recorded facts from derived values and analyst interpretation.
- [ ] Treat stale, unknown, or conflicting values as explicit limitations—not current facts.
- [ ] Confirm that geometry alone is not being used to infer legal boundaries, public access, route safety, current transit service, or facility conditions.

## 4. Review privacy and publication scope

- [ ] Produce only the minimum necessary aggregate or generalized output.
- [ ] Inspect both published assets and supporting files for personal or child-identifying information and individual movement traces.
- [ ] Consider whether small counts, precise locations, joins, or repeated releases could re-identify people; aggregation alone is not a privacy guarantee.
- [ ] Document the human privacy review and any generalization/suppression applied.
- [ ] Confirm each material claim has a source and retrieval date, and that field-verification gaps are plainly disclosed.

## 5. Build the product bundle

Create `data/YYYY-MM-DD-lowercase-slug/` with the files required by the [product standard](product-standard.md):

- `product.json`
- `sources.json`
- `method.md`
- the declared publication asset(s)

Start from [templates](../templates/). Replace every placeholder and ensure asset paths are relative, contained within the bundle, and match the declared manifest. Include geographic scope, publication date, limitations, and correction contact/path.

Run:

```sh
python -m unittest discover -s tests -v
python scripts/validate_products.py
python scripts/validate_source_rights.py
```

The structural validators are necessary but insufficient: they do not prove source accuracy, license interpretation, privacy safety, scientific validity, or that field verification actually occurred.

## 6. Review, publish, and maintain

- [ ] A reviewer independent of the author checks the source evidence, method, outputs, rights, privacy, and limitations.
- [ ] Re-run the documented method and compare output hashes or declared expected results.
- [ ] Confirm the bundle passes CI at the exact proposed commit.
- [ ] Merge only after all blocking findings are resolved; record the product date and provenance.
- [ ] Define a review/expiry trigger based on source update cadence and product risk.
- [ ] Correct errors with a dated, visible correction history; do not silently rewrite published claims.

## Release decision

Use exactly one outcome:

- **BLOCKED** — any rights, privacy, provenance, correctness, or review gate is unresolved.
- **READY FOR REVIEW** — evidence and bundle are complete; independent review and CI remain.
- **APPROVED FOR PUBLICATION** — all required human reviews and exact-commit checks passed.

A passing script or green badge alone never changes a product to approved.

## 7. Preserve release-evidence integrity

When using the signed release-attestation and JSONL history tools, treat the history as an integrity aid—not as a source-rights decision or a substitute for independent release review.

- [ ] Run the release-evidence verifier against the exact bundle before signing; signing must fail closed when independent verification fails.
- [ ] Verify each signed attestation with an explicitly trusted public key and the expected manifest. A matching file hash in the history proves byte consistency only; it does not verify the attestation signature.
- [ ] Keep the history and attestation files in controlled storage with access controls and backups. Retain an independently protected checkpoint of the latest history hash outside the writable history location; compare it during review to detect whole-history replacement or truncation.
- [ ] Serialize all history append operations. The writer uses atomic replacement to avoid partial-file writes, but it does **not** provide a multi-writer lock; concurrent appenders can overwrite each other's updates.
- [ ] After append, verify the complete chain and all referenced attestation hashes. Preserve the exact commit, command output, trusted-key fingerprint, and external checkpoint used for the release decision.
- [ ] Keep release authorization separate: signatures, hashes, and successful CI do not grant reuse rights or authorize publication. A blocked manifest remains blocked until the required source-rights, privacy, quality, and human-review gates are independently resolved.

Example commands (adjust paths to the reviewed bundle and key):

```sh
python scripts/verify_release_evidence.py --help
python scripts/release_history.py verify --history path/to/history.jsonl --attestation-dir path/to/attestations
```

Use the attestation verifier's documented CLI and explicit trust configuration for signature checks. Do not infer the command-line options from this checklist; confirm them with `--help` for the checked-out commit.
