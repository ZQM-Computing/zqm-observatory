# Method

## Question and intended use

State the decision or question this product supports and who should use it.
Name important non-goals and situations where this product must not be used.

## Inputs and retrieval

For every input, identify the exact dataset, publisher, URL, retrieval date,
license/terms, relevant version or query, and fields used. The companion
sources.json file must list these sources and the claims each supports.

## Processing steps

List the steps in execution order, including filters, joins, coordinate
reference systems, units, null handling, geometry repair, aggregation,
exclusions, and any thresholds. Include commands or code where practical.

## Quality checks

Describe validation performed, expected invariants, observed results, known
failure modes, and what was not tested. Do not describe an unrun check as
passed.

## Field verification

State what was checked, when, by whom, and how. If no field verification
occurred, state that limitation plainly and explain how it affects the result.

## Privacy and aggregation

Explain how individual-level records, personal data, and identifiable
children's data are excluded. Record the human privacy review in product.json.
The automated validator checks declarations only; it cannot inspect the
substantive privacy properties of the data.

## Limitations and reproduction

List temporal, spatial, coverage, accuracy, licensing, and reproducibility
limits. Give enough steps for another person to reproduce the product.
