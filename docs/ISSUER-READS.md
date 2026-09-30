# Source-bound issuer-result reads

The Business desk currently publishes curated reads for three matched Item 2.02 issuer results: Amazon, Eli Lilly and Home Depot. They answer a first-pass investor question: what did the issuer say drove the quarter, what unusual item changes the interpretation, and what guidance or assumption matters next? This is not a complete company model, a consensus comparison, an independent verification of management's explanation or an investment recommendation.

## Evidence boundary

Each factual editorial claim in `data/issuer_reads/catalog.json` names the issuer CIK, exact 8-K accession and reporting quarter. Its short source cue must occur in a cited line of the retained EX-99.1 visible text; every line and the raw document have SHA-256 checks. The build publishes only when that event is the latest selected Item 2.02 event for the CIK and has a separately verified same-quarter 10-Q dossier. A new event removes the older curated read from the live dossier until a new reviewed read is prepared. The SEC can recapture identical visible text with different raw HTML bytes; in that case both raw hashes are checked and the **entire** normalized visible document must still equal the reviewed edition. A changed visible document, cited line, period or cue fails validation. Up to 25 source-cue words per issuer are used; the full exhibit remains at the SEC link.

The exhibit may be **furnished**, so its operating explanations, segment measures, comparable sales and forecasts are called *issuer-reported*, never independent filed 10-Q facts. The separately linked 10-Q supplies the consolidated reported figures below the read. The companyfacts join does not verify management's causal bridge, segment accounting, guidance, tariff assumption or non-GAAP measure. The open question is Public Record analysis, not an issuer statement or an established forecast.

## Current edition and refresh rule

The current three reads cover eight claim cards across pharmaceuticals, cloud/retail and home improvement. Amazon's nonoperating pretax investment income is not subtracted directly from after-tax net income; the tax effect is not established here. Lilly's Key Products category and non-GAAP EPS outlook are issuer defined. Home Depot's total-sales growth and comparable-sales growth are different measures.

Source collectors refresh daily on the site's schedule, but **these editorial reads do not automatically rewrite themselves**. The exact-accession gate prevents an old interpretation from attaching to a new quarter. Editors must review the successor exhibit, revise the catalogue's claim text and locators, run tests/build, obtain fresh content and PM approval, and publish a new version. Three reads among 25 selected registrants are a pilot, not complete Business coverage. The [completion audit](GOAL-AUDIT.md) tracks the broader repeat-utility gap.
