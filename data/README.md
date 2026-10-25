# Data

## No data products yet

This directory holds Observatory data products. It is intentionally empty
today. No dataset, map, or digest has been verified and published, and
nothing here claims otherwise.

## Product bundle standard

Each dated product must follow the [machine-checkable product standard](../docs/product-standard.md). Reusable metadata, source-list, and method templates are in [templates/](../templates/). CI validates bundle structure and declared privacy fields; human review remains responsible for factual accuracy, licensing, substantive privacy, and field verification.

## What belongs here

A product lands here only when it passes the verification standard in
[methods](../docs/methods.md): named public sources with retrieval dates,
a repeatable method, field verification where place conditions matter,
aggregates-only reporting, and a date on the product itself. The proposal
process is in [Contributing](../CONTRIBUTING.md).

## License gate

Data products published from the Observatory are licensed under CC BY 4.0,
with attribution to their stated sources, and upstream source licenses
still apply to their own data. The DATA-LICENSE file that backs this
lands with the first data product, as described in
[roadmap](../docs/roadmap.md). It is not added before then, because there
is no data product for it to cover yet.

## Layout

When products arrive, each one lives in its own dated subdirectory with
its data, its method note, and its source list together, so a reader can
retrace any claim without hunting across the repository.
