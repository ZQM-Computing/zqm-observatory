# Metadata-only source preflight

Run this tool only when a fresh metadata snapshot is useful for reviewing a candidate source. It requests ArcGIS layer metadata, not feature records.

```sh
python scripts/audit_source_metadata.py --output build/source-metadata-preflight.json
python scripts/audit_source_metadata.py --strict --output build/source-metadata-preflight.json
```

The command writes a timestamped JSON report with HTTP status, content type, byte count, SHA-256 of the raw response, layer identity, geometry type, spatial reference, field definitions, declared domains, copyright/description text, and the source's existing rights decision. The output file should be reviewed before committing; reports are evidence snapshots, not automatically trusted source truth.

## Safety boundaries

- Only HTTPS ArcGIS layer URLs on `maps5.vcgov.org` matching `FeatureServer/<numeric-layer-id>` are eligible.
- Requests append only `f=pjson`; no `where`, `outFields`, geometry, pagination, or feature query parameters are issued.
- Redirects are not followed. The response is capped at 2 MB and the request timeout is 15 seconds.
- Non-layer sources such as the VOTRAN document index are skipped without a network request.
- Unexpected feature payloads, malformed metadata, non-JSON responses, and oversized responses fail closed.
- The report repeats the source's current rights decision. It cannot approve collection, establish a license, or authorize publication.
- No data rows, attachments, GTFS archives, or bulk datasets are downloaded.

This is a bounded metadata reconnaissance aid, not a replacement for source-specific terms review, field-level data QA, privacy review, or field verification. Never commit credentials or unreviewed data captures.
