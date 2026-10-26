# Data product standard

Every published product lives in its own directory under data/, named
YYYY-MM-DD-lowercase-slug. A product bundle contains:

- product.json: scope, date, license, source references, data files,
  field-verification status, and recorded privacy review.
- sources.json: exact source identifiers, publisher, HTTPS URL, retrieval
  date, license/terms, and the claims each source supports.
- method.md: repeatable processing steps, checks, limitations, and field
  verification details.
- The actual published data asset or assets named in product.json.

Templates live in ../templates/. Copy them into a new dated product directory
and replace every placeholder before proposing publication.

## Automated structural gate

Run:

```sh
python -m unittest discover -s tests -v
python scripts/validate_products.py
```

The validator checks required metadata, duplicate JSON keys, UTF-8 decoding,
ISO dates and chronology (sources and privacy review must predate or match publication), directory/date agreement, unique and matching source identifiers,
HTTPS source links and valid ports, source retrieval dates, portable canonical
relative asset paths (including rejection of Windows drive-prefixed paths),
path traversal, symlinks across the whole bundle,
undeclared sidecar files, field-verification disclosure, and recorded
privacy-review flags. It uses only the Python standard library.

The validator does **not** prove that sources are accurate, URLs are reachable,
licenses permit a particular use, privacy declarations are true, field
verification occurred, or analysis is scientifically valid. Those remain
human review gates. Do not describe a passing structural check as a product
certification.

## Publication checklist

Before merge, reviewers must confirm:

1. Every material claim is traceable to the named source and retrieval date.
2. The method is reproducible and the submitted outputs match it.
3. CRS, units, geometry validity, temporal coverage, missing values, and
   spatial/attribute joins are appropriate for the product.
4. Field-verification status and any unverified conditions are stated honestly.
5. A human privacy review confirms there are no individual tracks, personal
   data, or identifiable children's data in the output or supporting files.
6. Source licensing, attribution, and redistribution terms have been checked.
7. The product has a clear geographic scope, publication date, limitations,
   and correction path.
