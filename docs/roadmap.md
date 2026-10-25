# Roadmap

Stages, not dates. No stage is promised for a calendar day; a stage is done
when its gate is met and verified.

## Stage 0: repository and direction

Done. The repository exists with its license and README: scope, focus,
principles, and the shape of what it ships. The fleet stack (PostGIS,
GeoServer, orchestration, collection, and intelligence tooling) is being
installed node by node. Nothing here is a live service yet.

## Stage 1: documentation and standards

This stage. A real docs tree (scope, methods, data sources, roadmap), a
contributing standard, a data directory that honestly states it holds no
products yet, and repository hygiene (prose checks) so new content is
checked on every change.

Gate: the docs describe a standard a product can actually be judged
against, and the repository contains no claim it cannot support.

## Stage 2: first data product

Use the [first-product release gate](first-product-release-gate.md) as the working checklist from question selection through rights review, QA, privacy review, bundle validation, and publication approval.

The first dated, sourced, verified product lands in the data directory.
The most likely shape is a community brief or a family guide for one
Volusia County community: aggregated, field-verified where place
conditions matter, with its source, retrieval date, and method inside the
product.

Gate: the product passes every item of the verification standard in
[methods](methods.md). At this stage, and not before, the DATA-LICENSE
file lands with the product: data products are licensed CC BY 4.0, with
attribution to their stated sources, and upstream source licenses still
apply to their own data. The README already states this forward intent;
the file is the backing that arrives with the first product itself.

## Stage 3: recurring products

If Stage 2 holds up, the shape widens: a dated weekly intel digest,
community briefs for more communities, living map layers, and a STAC
imagery catalog, as described in the README's list of what the Observatory
ships. Each new product passes the same verification standard; the
standard does not loosen because a first product landed.

Gate: every product stays dated, sourced, verified, and aggregated, and
corrections stay public and dated, as described in [methods](methods.md).

## What is deliberately not on this roadmap

No product is planned that needs individual-level data, private data, or
paywalled data. No product is planned that cannot state its source,
retrieval date, and method. If a proposed product cannot meet the
standard, the roadmap does not bend for it; the proposal waits or is
declined. See [Contributing](../CONTRIBUTING.md).

## Related documents

- [Scope](scope.md): what the Observatory covers, and where it starts.
- [Methods](methods.md): the verification standard.
- [Data sources](data-sources.md): the public source categories.
