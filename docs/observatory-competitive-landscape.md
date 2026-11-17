# ZQM Observatory competitive landscape and feature naming

Research date: **November 17, 2026**. Scope: the Observatory's question-to-map
prototype and its position within **ZQM Computing**. This research does not
evaluate ZQM Labs products.

## Decision

Use **MapExplain** as the provisional feature name within **ZQM Observatory**,
published by **ZQM Computing**. Describe the value as **traceable location
analysis**, with the explanatory line:

> Ask about places. See the map, sources, and steps.

Do not retain Location Answers as a distinctive product name. It already appears
in adjacent vendors' location-intelligence messaging. Do not present this
prototype as a general AI GIS, a verified decision service, or a production
alternative to the platforms below.

Public searches did not identify a directly competing branded GIS product named
MapExplain in the results reviewed. That is a preliminary screening observation,
not trademark, company-name, domain-registration, package-name, or social-handle
clearance. Use the existing ZQM identity and domain context; no registration,
purchase, trademark application, or paid service was performed.

## Method and evidence limits

The review covers **13 competing offerings** and **15 candidate names** using
two search indexes and vendor-owned product pages, documentation, first-party
repositories, or creator statements. Technical comparisons rely on primary
sources. Exact names and relevant spaced variants were searched; unrelated
programming identifiers were distinguished from actual products.

Vendor descriptions below are **documented vendor claims**, not independently
tested performance, adoption, legal compliance, source permission, or delivery
quality. A missing feature on a reviewed page does not establish that the vendor
lacks it. No competitor account was created, paid plan purchased, private
workspace accessed, or benchmark executed. Search-index timestamps were not
treated as product launch dates.

Current ZQM behavior is grounded in the code and [verification record](../apps/map-explain/QA.md).
Its methods run locally on invented Providence layers and bounded user-supplied
Point data. This is an engineering demonstration with explicit release gates,
not an operational public-data service.

## Closest competitors

The last column is an assessment for ZQM, not an assertion about a competitor's
missing capabilities.

| Offering | Documented audience and job | Relevant overlap | Implication for ZQM |
| --- | --- | --- | --- |
| [Felt / Felt AI](https://felt.com/about) | Teams using shared spatial data across operations and planning | Plain-language spatial questions, connected sources, live maps, dashboards, and apps | Asking a question and receiving a map is established category behavior, not a differentiator. |
| [Atlas / Navi](https://atlas.co/) | GIS and non-GIS teams in infrastructure, energy, property, and operations | Conversation-generated maps, multi-step workflows, and an inspectable/editable workflow canvas | Explainable steps and team accessibility are already explicit competitor promises. |
| [CARTO AI Agents](https://docs.carto.com/carto-user-manual/ai-agents) | Organizations with governed spatial data and specific business questions | Configurable agents, semantic models, geospatial tools, and MCP extensions inside maps | Domain definitions and well-scoped workflows matter more than another generic chat surface. |
| [GIS Cloud / Ask AI](https://manual.giscloud.com/knowledge-base/ask-ai-the-in-app-assistant/) | Map, field-data, and operations users | Conversational layer analysis, selections, map work, forms, and app generation | A chat panel and sample prompts alone provide little competitive separation. |
| [Geobble](https://geobble.com/) | Technical and domain teams preparing usable web maps | File/PostGIS sources, plain-language filters and geoprocessing, review, cartographic editing, and publication | Reviewability is also part of a competitor's end-to-end source-to-map story. |
| [Aino](https://www.aino.world/) | Architecture, urban-planning, and built-environment teams | Site research, connected planning data, source-tracked analysis, reusable layers, and reports | This is a close positioning reference for environmental/planning service buyers. Avoid implying equivalent data coverage or submission readiness. |
| [Locus](https://www.locusintel.io/) | Brokers, site-selection professionals, entrepreneurs, and operators | Site comparisons, evidence-aware reports, location research, an assistant, and permissioned MCP access | Specific decision workflows and clear demo-versus-paid boundaries are stronger than a broad location-intelligence label. |

## Adjacent alternatives and technical substitutes

| Offering | Documented job | Relevant overlap | Implication for ZQM |
| --- | --- | --- | --- |
| [CleverMaps / Shared Logic](https://www.clevermaps.ai/product/shared-logic) | Deliver location enrichment, combined metrics, and ranked scores into other business systems | Source/method traceability, consistent scoring, APIs, and agent access described as early access | Traceable numbers and consistent logic are already marketed. Agent availability must be reported at its stated stage. |
| [MapGO](https://mapgo.io/) | Geographic lookups, distances, file tools, and US-address context reports | Browser-accessible measurements and named-source location outputs | Useful point-based answers and reports can be sold without positioning everything as AI. Its property report is described as point surroundings, not a parcel record. |
| [xMap Flows](https://flows.xmap.ai/compare/) | Turn supplied location data and business signals into recurring workflows and actions | Location scoring, maps, data blocks, and operational delivery | A data-and-workflow vendor competes for the business result, not only the mapping interface. Its comparisons are its own positioning, not neutral assessments of other vendors. |
| [GeoAgent for QGIS](https://geoagent.readthedocs.io/en/stable/index.html) | Run geospatial processing through natural-language requests in QGIS | QGIS algorithms, step/parameter logs, reusable model export, and local Ollama support | Open-source processing, local-model options, and execution logs are not unique by themselves. This is a desktop substitute rather than the same browser product. |
| [Mapdex](https://mapdex.ai/) | Georeference scans and extract/review geometry for GIS or CAD delivery | Evidence attached to results, uncertain-result review, and validated exports | Evidence-oriented map work is a competitive theme even in an adjacent data-preparation workflow. No advertised positional-accuracy figure was independently verified. |
| [PlaceBrief](https://placebrief.com/) | Embed source-linked destination context assembled from news, events, weather, and public signals | Geographic questions, sources, briefings, widgets, and APIs | This overlaps the broader Observatory's planned briefs, but differs from the current deterministic point-analysis demo. Do not use PlaceBrief as a new feature name. |

## What the research changes about the product story

### Conversation is a usability pattern, not the product advantage

Felt, Atlas, CARTO, and GIS Cloud all explicitly connect ordinary-language input
to geospatial work. A headline that amounts to asking a question and getting a
map describes a competitive category. It does not explain why a buyer should
choose ZQM.

The present prototype also does not implement unrestricted conversation. It
matches a fixed set of English patterns and declines unsupported requests.
Its public copy should accurately describe supported questions and visible
calculation steps, rather than imply a general model or an autonomous GIS agent.

### Showing the method is necessary, but not exclusive

Atlas documents an editable workflow canvas. Geobble emphasizes inspection and
review before publication. CleverMaps describes figures tracing to source and
method. GeoAgent documents parameter/step logs and model export. These primary
sources rule out claiming that explanation, provenance, or reusable processing
is an unmet market by itself.

The actionable question is whether ZQM can demonstrate a specific workflow with
well-defined inputs, correct calculations, understandable limitations, and a
useful handoff. That proposition requires evidence from representative tasks,
not a new adjective in the feature name.

### Domain-specific outcomes are a better starting point

Aino speaks to planning teams and reusable site research; Locus organizes its
offer around location decisions and reports. CARTO's
[first-party implementation lessons](https://www.carto.com/blog/lessons-building-ai-agents-geospatial-analysis/)
also emphasize choosing a bounded use case, describing the data semantics, and
testing the questions people actually ask.

For ZQM, a reasonable proposed audience is a small consulting or planning team
that needs a reviewable preliminary GIS result with a map, criteria, source
register, method, and explicit gaps. That is a positioning hypothesis informed
by ZQM Computing's services direction. It is not proof of demand, a launched
offer, or a claim that this prototype currently handles real parcels or permit
decisions.

### Claims must follow demonstrated capability

| Message | Evidence status for this prototype | Wording decision |
| --- | --- | --- |
| Supported plain-language spatial questions | Implemented, bounded patterns | May describe with examples and explicit limits. |
| Calculations, ranked rows, local map, and method notes together | Implemented and tested on the demo | Lead with this reviewable experience. |
| Files processed inside the current browser tab | Implemented for bounded supported point uploads | Describe the actual processing path; do not equate it with broad regulatory compliance. |
| Source notes and draft export status | Implemented, including blocked publication metadata | Describe as context for review, not source-license approval or factual certification. |
| General AI conversation or arbitrary geoprocessing | Not implemented | Do not advertise. |
| Real-source automatic discovery, live feeds, or nationwide screening | Not implemented by this app | Keep outside current feature claims. |
| Parcel-boundary analysis, routed access, or regulatory conclusions | Not implemented or not supported | Do not imply site-selection or permitting readiness. |
| Fully offline availability | Not established by loaded-tab local calculations | Do not claim cold-start offline support. |
| Mobile or production readiness | Still subject to documented verification | Do not turn a rename or green unit tests into a release claim. |

## Recommended positioning

**Publisher:** ZQM Computing.

**Platform:** ZQM Observatory — traceable place-based research and analysis.

**Provisional feature:** MapExplain — traceable location analysis.

**User value:** ask a supported location question and inspect the map, results,
source notes, and calculation steps together.

**Current status:** synthetic engineering demonstration. Source permissions,
privacy, factual quality, and product release remain separate gates.

Keep one brand hierarchy rather than launch another independent SaaS identity.
Lead with the concrete user task; show the name, platform, and publisher together
at first encounter. For future service marketing, connect a demonstrated workflow
to a scoped ZQM Computing project inquiry. Do not imply this prototype already
provides the data, coverage, account controls, integrations, or delivery maturity
advertised by the commercial platforms.

## Candidate-name collision screen

These are public-web observations and naming judgments, not legal determinations.
Technical identifiers and generic phrases are recorded because they also weaken
search distinction even when they do not identify a competing company.

| Candidate | Evidence found | Decision |
| --- | --- | --- |
| Location Answers | [xMap](https://flows.xmap.ai/compare/) and [CleverMaps](https://www.clevermaps.ai/product/shared-logic) use the phrase in their messaging. An indexed MapGO copy also surfaced with it; the canonical homepage had different wording when opened. | Reject as the feature's distinctive name. |
| MapSift | [MapSift](https://mapsift.com/) advertises a maps-based lead product; a separate [public GIS repository](https://github.com/johnsilverio/mapsift) also uses the name. | Reject. |
| Placeframe | Existing [place-identification game](https://placeframe.kballenegger.com/) and [spatial-computing package](https://openupm.com/packages/org.outernet.placeframe/) use the name. | Reject. |
| MapThread | A [first-party WordPress mapping/storytelling repository](https://github.com/randomwire/Mapthread) uses Mapthread. | Reject. |
| PlaceBrief | [Existing destination-intelligence service](https://placebrief.com/) has direct thematic overlap with Observatory briefs. | Reject. |
| GeoClarify | A [creator's public GeoClarify AI statement](https://www.linkedin.com/posts/muhammad-atif-bilal-8315118b_mineralexploration-economicgeology-geochemistry-activity-7491568183498264576-UDFn) describes mineral exploration and geospatial decision support. This establishes public use, not an independently verified commercial offering. | Reject as a fresh, unqualified identity. |
| MapReason | [MapReason-OSM](https://github.com/Vi-Sri/mapreason-osm) is an existing map-reasoning benchmark with a closely related technical audience. | Reject. |
| PlaceQuery | [Logi's official documentation](https://clm.logianalytics.com/rdPage.aspx?Drilled=True&iLabel=PlaceQuery&iName=PlaceQuery&iType=Attribute&itemID=2351&lnkpg=2&rdReport=ElementRefDetail) uses PlaceQuery for a mapping attribute; other software APIs also use the identifier. | Weak search distinction; do not prefer. |
| QueryTrail | A [developer's first-party description](https://nopecode.com/2014/08/10/query-trail.html) and [Rust API documentation](https://docs.rs/juniper-from-schema/latest/juniper_from_schema/struct.QueryTrail.html) establish software uses. | Reject. |
| MapMethod | A [NWCG geospatial standard](https://fs-prod-nwcg.s3.us-gov-west-1.amazonaws.com/s3fs-public/2023-08/910-fmu-strategic-objective-polygon.pdf) uses MapMethod as a derivation-quality field. | Generic technical terminology; weak benefit clarity. |
| GroundQuery | [NVIDIA's official documentation](https://docs.omniverse.nvidia.com/kit/docs/omni_physics/107.2/extensions/ux/source/omni.physx.vehicle/docs/collision_filtering_and_materials.html) uses it for physics ground queries. | Technical naming noise and poor fit for non-GIS users. |
| Map Inquiry | [Four Corners Mapping](https://www.fourcornersmapping.com/map-inquiry) uses the phrase for a GIS service page; an [Esri-hosted county case study](https://www.esri.com/content/dam/esrisites/en-us/newsroom/arcuser/fall-2015.pdf) describes a Map Inquiry tool. | Do not treat it as a distinctive new GIS identity. |
| Spatial Inquiry | [GIS course terminology](https://catalog.wellesley.edu/index.php?code=ES206&pos=5&view=course&year=2026-2027) and [an existing GIS capability label](https://baykartech.com/en/network-centric-software/) use the phrase. | Descriptive category wording, not a strong distinct name. |
| MapRationale | Reviewed results did not identify a directly competing branded GIS product; similar words appeared in ordinary map/planning prose. | Possible reserve; longer and more technical than the preferred candidate. |
| MapExplain | Two-index exact and spaced-name searches did not identify a directly competing branded GIS product. Similar MapExplainer code/tutorial terms and MapEx wayfinding software surfaced. | Preferred provisional name, always qualified with ZQM Observatory and a plain-language descriptor. |

## Shortlist and rationale

The scores below are qualitative judgments, not legal-risk scores or measured
customer preferences.

| Candidate | User-value clarity | Distinction in reviewed results | Fit with Observatory | Limitation |
| --- | --- | --- | --- | --- |
| **ZQM Observatory — MapExplain** | Strong when paired with the map/source/steps descriptor | Best of the screened shortlist; no direct product collision identified | Keeps the established platform and publisher in the foreground | Provisional; no registry/domain/handle clearance. |
| ZQM Observatory — MapRationale | Emphasizes the reason behind a mapped result | No direct branded competitor identified | Fits traceability and analytical review | More abstract and harder to say for nontechnical users. |
| ZQM Observatory — Spatial Inquiry | Describes asking geographic questions | Existing generic and technical uses | Coherent as a section label | Too generic and academic to function well as a distinctive product name. |

MapExplain is preferred because it supports explaining a result without claiming
that the result is authoritative, certified, universally correct, or generated
by a general-purpose AI. Its public identity should remain **ZQM Observatory —
MapExplain**, not an unqualified independent brand.

## Commercial and development implications

1. Choose one buyer task before expanding the application. Candidate tasks include
   comparing approved point locations, identifying illustrative service gaps, or
   delivering a documented preliminary GIS screening through a separately scoped
   service. Validate the actual task with potential buyers.
2. Use a small representative benchmark: valid inputs, malformed inputs,
   unsupported questions, known expected results, export correctness, and review
   time. Require correct interpretations and explicit refusals, not just fluent
   explanations or appealing maps.
3. Before advertising a real-source workflow, establish source rights, actual
   geography coverage, CRS and geometry handling, freshness, privacy review, and
   the exact analyst handoff. Keep missing requirements visible in the evidence.
4. Prove why a buyer would pay. For context, Locus's reviewed page advertised a
   $15 one-time location report and monthly $49/$99/$199 plans. Those are vendor
   offers observed on this research date, not verified purchases, comparable ZQM
   pricing, or proof that the current prototype can replace them.
5. Treat names as a final layer over a useful workflow. Do not spend on a new
   domain, paid API, or identity program while user value and delivery remain
   unproven.

## Source register and follow-up limits

All linked competitor pages and naming evidence were retrieved or surfaced in
the November 17, 2026 review. The named vendor/product pages are primary sources;
the GeoClarify item is explicitly a creator statement, not a corporate product
audit. The name screen includes exact forms and sensible space variants using
both search indexes, with particular cross-checks for MapExplain, MapRationale,
MapReason, GeoClarify, and QueryTrail.

No exhaustive company-register search, trademark-register clearance, registrar
availability check, package reservation, social-handle reservation, or legal
opinion is claimed. No market-share, revenue, conversion-rate, positional-accuracy,
time-saving, or competitor security claim was independently established.
