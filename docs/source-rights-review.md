# Source rights review workflow

**Purpose:** record whether a specific upstream dataset may be collected, transformed, combined, and republished for a defined Observatory product. This is an evidence log and decision aid, not legal advice.

**Default state:** `BLOCKED_PENDING_REVIEW`. A public URL, downloadable file, blank copyright field, “open data” label, or warranty disclaimer does not by itself establish permission to redistribute the source or publish derivatives.

## 1. Review one item at a time

Do not approve an entire portal or service based on one landing-page statement. Create a separate review record for each dataset or layer when its publisher, terms, attribution, or intended use can differ.

| Field | Required evidence |
| --- | --- |
| Source identity | Publisher/steward, dataset title, stable portal item ID, service URL, layer ID, version/date |
| Evidence of terms | Exact terms/license URL, captured text or archived evidence, retrieval timestamp (UTC), displayed version/date |
| Intended use | Internal inspection, transformation, spatial join, public map, redistribution of raw data, redistribution of derived data |
| Obligations | Required attribution, notices, share-alike, access restrictions, privacy/security limits, fees, expiration or update conditions |
| Decision | `APPROVED`, `APPROVED_WITH_CONDITIONS`, `INTERNAL_ONLY`, `BLOCKED_PENDING_REVIEW`, or `REJECTED` |
| Rationale | Exact clause supporting the decision, scope of permission, unresolved ambiguity, reviewer and review date |
| Recheck trigger | Terms change, new item/version, new intended use, new joining source, or material change in output |

Never infer that permission for internal viewing also allows redistribution, commercial use, bulk extraction, or derivative publication. Do not assume the Observatory's CC BY 4.0 output license overrides upstream conditions.

## 2. Decision rules

1. **Identify the actual licensor.** Confirm the publisher and the steward empowered to grant the requested rights. A third-party catalog or mirror is not automatically the licensor.
2. **Read the item-level terms.** Check the dataset page, attached metadata, service terms, portal terms, and any linked license. Preserve evidence of which terms applied on the review date.
3. **Match the use to the grant.** Record separately whether the terms permit access, internal processing, transformation, spatial joins, public display, redistribution of raw records, and redistribution of derivatives.
4. **Check conditions.** Capture attribution text, notices, share-alike or database obligations, limits on bulk access, privacy restrictions, and any incompatible downstream license.
5. **Resolve ambiguity in writing.** Ask the data steward to identify the applicable license and explicitly answer the intended use. Save the request and response with the review record. Silence is not approval.
6. **Make a scoped decision.** A conditional approval names the permitted output and required conditions. Do not generalize one approval to neighboring layers or future versions.
7. **Recheck before release.** Verify the terms still apply to the exact captured version and intended distribution. Preserve the evidence alongside the product's source manifest.

If a material permission is unclear, leave public publication blocked. Internal-only use is permitted only if the available terms themselves allow that use; it is not a default workaround for prohibited or uncertain access.

## 3. Suggested request to the data steward

Adapt this message to the exact dataset; do not send it automatically.

> We are evaluating the [dataset title, portal item ID, service/layer ID, URL] for a documented, public-interest geospatial inventory. Could you identify the license or terms governing this specific layer and confirm whether they permit (1) automated download/capture, (2) transformation and spatial joins, (3) public display of features, and (4) redistribution of the original data or derived datasets under CC BY 4.0? Please provide required attribution text, any restrictions or notices, and the date/version of the applicable terms. If your office does not administer these rights, please direct us to the responsible data steward. We will keep publication on hold until the terms are clear.

## 4. Reusable decision record

Copy this block into the relevant source register or a restricted review log. Do not commit private correspondence or personal contact details unless publication is appropriate.

```yaml
source_title: ""
publisher: ""
steward_role_or_office: ""
portal_item_id: ""
service_url: ""
layer_id: ""
source_version_or_updated_at: null
terms_url: ""
terms_retrieved_at_utc: ""
terms_evidence_path_or_reference: ""
intended_product: ""
intended_uses:
  internal_capture: false
  transformation: false
  spatial_join: false
  public_display: false
  raw_redistribution: false
  derived_redistribution: false
required_attribution: null
obligations_or_restrictions: []
decision: BLOCKED_PENDING_REVIEW
decision_rationale: ""
reviewer: ""
reviewed_at_utc: ""
written_clarification_reference: null
recheck_triggers:
  - source terms change
  - source version changes
  - intended use or output license changes
```

The booleans above are fields to be filled from evidence, not assumptions. A value of `false` means “not approved for this use,” not necessarily “the publisher prohibits it.”

## 5. Publication gate

A source may be included in a public product only when all applicable checks pass:

- [ ] The exact source and rights holder/steward are identified.
- [ ] Item-level terms are captured with a timestamp and stable reference.
- [ ] The terms support every intended collection and publication action.
- [ ] Attribution and other obligations are recorded and implemented.
- [ ] Ambiguity is resolved by authoritative written clarification, where needed.
- [ ] The proposed output license is compatible with the source terms.
- [ ] The review is linked from the product's `sources.json` or source register.
- [ ] The review will be repeated if the source version, terms, or use changes.

A completed checklist is an auditable review, not a guarantee of legal sufficiency. Escalate material ambiguity to qualified counsel or the rights holder rather than guessing.

## Related records

- [Volusia source register](volusia-source-register.md)
- [Trail evidence matrix and collection gate](trail-evidence-matrix.md)
- [Data product standard](product-standard.md)
- [Methods](methods.md)
