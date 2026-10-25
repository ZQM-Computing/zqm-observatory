# Contributing

## What belongs here

Proposals for Observatory data products: a community brief, a family
guide, a map layer, a digest, or a method others can reuse. A proposal is
a draft product plus its evidence, not an idea alone.

Read [methods](docs/methods.md) and [data sources](docs/data-sources.md)
before proposing. A proposal that does not meet the verification standard
will wait until it does.

## How to propose a product

Open a pull request that contains the product and everything below, in
the product itself or in the pull request description:

1. The question the product answers, and why it matters to a resident,
   visitor, or family.
2. Every source used, named as an exact dataset with a retrieval date.
3. The method, written so a second person can repeat it.
4. Field verification for every place condition that matters, or a plain
   statement of where verification has not happened.
5. An aggregation plan: how the product reports only aggregates, with no
   individual tracks, no personal data, and no children's identifiable
   data anywhere in it.
6. License notes: upstream source licenses respected, attribution given
   to the stated sources.

## The verification standard

Before a product is merged, it must pass all of these, from
[methods](docs/methods.md):

1. Every claim traces to a named public source with a retrieval date.
2. The method is written so a second person can repeat it.
3. Place conditions that matter are field-verified, or the gap is stated.
4. All reporting is aggregated; no individual, personal, or children's
   identifiable data appears anywhere in the product.
5. Upstream source licenses are respected, and attribution is given to
   the stated sources.
6. The product is dated, so a reader can tell how old its picture is.

## What is never accepted

- Credentialed, paywalled, or private data.
- Individual-level records, personal data, or children's identifiable data.
- A product whose source, retrieval date, or method cannot be stated.
- A claim that cannot be retraced to a public source.

## Licenses

Code in this repository is licensed under the Apache License 2.0 (see
LICENSE). Data products published from the Observatory are licensed under
CC BY 4.0, with attribution to their stated sources; the DATA-LICENSE file
lands with the first data product, as described in
[roadmap](docs/roadmap.md). Upstream source licenses still apply to their
own data.

## Style and checks

- Write in Markdown. Every file starts with a single top-level heading.
- Keep lines wrapped and headings, lists, and code fences separated by
  blank lines; the prose checks (markdownlint and link checking) run on
  every pull request.
- Link only to files that exist in the repository, and to real public
  source pages. A pull request with a broken internal link does not merge.

## Corrections

If a merged product turns out wrong, correct it in place with a dated
correction describing the change. Do not silently rewrite published
products.
