# Metadata-only ArcGIS layer audit

The utility `scripts/audit_arcgis_metadata.py` summarizes a **previously saved ArcGIS layer metadata JSON file**. It is intentionally offline: it makes no network requests and never calls a feature `/query` endpoint. Use it while rights are unresolved to review metadata already lawfully obtained; it does not authorize retrieval or redistribution.

## Example

```sh
python scripts/audit_arcgis_metadata.py ./captures/trails-layer.json \
  --source-url https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/32 \
  --rights-state BLOCKED_PENDING_REVIEW \
  --output ./reports/trails-metadata-audit.json
```

The source URL identifies the metadata represented by the local file; the program does not fetch that URL. Rights state must come from the item's documented rights-review record. The tool does not infer permission from a URL, copyright field, public accessibility, or an “as is” disclaimer.

## Report semantics

The report records layer identity, geometry, description, copyright text, spatial reference, field names, record limit, pagination capability, and warnings. It flags missing metadata, absence of an observed GlobalID field, and a positive record limit that merits pagination review.

A warning is a prompt for human review, not proof of a defect. In particular, lack of GlobalID does not mean records cannot be tracked; it means object-ID stability and version reconciliation need an explicit strategy.

## Validation

```sh
python -m unittest tests.test_audit_arcgis_metadata -v
python -m unittest discover -s tests -v
```

This is a metadata triage aid only. It does not establish source rights, metadata freshness, feature correctness, topology, attribute meaning, current public access, route service, safety, accessibility, or field conditions. No feature records are included in its output.
