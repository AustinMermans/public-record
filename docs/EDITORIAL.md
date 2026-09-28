# Editorial architecture

Direction agreed during the September 28, 2026 build: a newspaper-like public-record research publication. Its value is the comprehensive picture made from siloed evidence, not merely a larger collection of feeds. This is a product design for subsequent editions, not a claim that every desk or join already exists.

## Two navigation dimensions

Version 1.3 implements a cross-section front page and separate Economy, Business, Government & Politics, Disclosures, Outlook, Changes and official-announcement fronts, plus shared search/calendar tools. These fronts organize existing source coverage; they do not imply that the longer-term datasets below have all been ingested. The user explicitly requested a Changes landing page as well as its ledger.

Subject desks answer **what is happening?** Research tools answer **how can I investigate it?** Keep them distinct: a calendar, search, saved lenses, change log and source-health register are shared tools, not competing subject categories.

| Provisional desk | Reader question | Existing foundation | Next coverage gap |
|---|---|---|---|
| Economy | What changed in activity, inflation, employment and financing conditions? | FRED histories, BEA schedules, Fed statements, Treasury auctions | Reliable BLS schedule; dated official forecast ingestion |
| Business | What changed for a company and its competitive environment? | Disclosure/search infrastructure and selected court metadata | SEC submissions/company facts, issuer calendars, verified entity mapping |
| Policy & Politics | What is proposed, decided, funded or approaching a deadline? | Fed statements and Federal Register | Legislative proceedings, budgets, votes; no general political-news coverage yet |
| Law & Regulation | What changed in rules, enforcement and litigation? | Federal Register and three selected district-court feeds | Broader courts/enforcement and stage-aware document extraction |
| Science & Innovation | What new claims, approvals or technologies merit investigation? | USPTO reference channels | Patent ingestion, assignee mapping, relevant approval/reporting feeds |

Government is principally an **actor/publisher**, rather than an exclusive desk: a government item can affect all five subjects. Desks are many-to-many facets, not mutually exclusive buckets. Record type, publisher, geography, entities, legal stage, observation/publication/effective dates and evidence quality remain separate fields. A document's classification is not an assertion of its economic importance.

## Front-page hierarchy

1. Lead developments: a small, dated selection, with stated selection reasons rather than a fabricated significance score.
2. The economic backdrop: a few interpretable measures with observation periods and revision caveats.
3. Cross-cutting dossiers: connect a durable question across disclosures, history, stakeholders and next milestones.
4. What changed since the prior edition, and what happens next.
5. Desk briefs and the complete source-linked record beneath the synthesis.

Preserve the academic visual language: readable serif headlines, thin rules, restrained annotations and charts that answer a specific question. No decorative charts, endless ticker strips or implied newsroom completeness.

## The synthesis unit: a dossier

A dossier should have a specific question, a concise dated finding, a timeline and linked evidence. Each substantive sentence distinguishes reported fact, calculation, interpretation, forecast or unresolved question. Where relevant include contrary evidence, stale/missing sources and the next observation that could alter the conclusion. A shared company name alone is insufficient to establish a causal or legal relationship.

Example design, **not a current factual claim**: a healthcare-policy dossier could join an agency proposal, comment deadline, a named company's filed exposure, and litigation over the same policy. It must distinguish proposal from final rule, effective date from publication, and an allegation from a judgment. The business implication is a hypothesis unless evidence establishes the mechanism and scale.

Entity joins should retain authoritative identifiers (such as CIK, docket/court and patent identifiers), name aliases, join basis and unresolved ambiguity. Topic matches are research leads; verified entity identity and confirmed relationships are separate layers. Syndicated copies and subsequent stages of one proceeding should not become several independent pieces of corroboration.

## Corporate data and yfinance

Start with source filings, issuer disclosures, event dates and comparable financial facts. The [SEC submissions and XBRL APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) provide a natural foundation, subject to access requirements and actual collector availability. Preserve filing accession, reporting period, units, amendments and source footnotes; a ticker is not a permanent entity identifier.

Market prices can provide context, but should not become the organizing principle. The [official yfinance project](https://github.com/ranaroussi/yfinance) says it is unaffiliated with Yahoo and describes the Yahoo Finance API as intended for personal use, referring users to Yahoo's terms for data rights. Accordingly, do not treat the package's software license as permission to republish its data on this public site. A future public pricing panel requires confirmed redistribution rights, reliable timestamps and corporate-action methodology. No yfinance ingestion or data redistribution is enabled in this edition.

## Highest-value next increment

With the user-requested desk structure in place, deepen it with one narrow, source-verified dossier. Pair reliable corporate identity/filing coverage with existing regulatory and court evidence. Validate the joins and narrative against a human-readable evidence table. Extend saved lenses to capture changes so a returning reader can ask, “What changed in the subjects I follow?” Add new feeds when they close a demonstrated blind spot, not merely because an API exists.

## Readability update and next data layers

Version 1.1 ships full available economic histories, sampled ALFRED vintages behind a button, direct FOMC/GDPNow extraction, a real month calendar, procedural court-entry explanations and a six-company SEC dashboard. The homepage brief remains a place for later dated original reporting; do not fill it with generic commentary merely to occupy the space. Every visible sentence should supply evidence, a useful distinction, a decision-relevant limitation or an action.

Political disclosures and transaction-level insider activity need separate schemas. Candidate/committee campaign totals should use comparable reporting periods or election cycles; cumulative flows reset at explicit boundaries and account for amendments/refunds. Holdings are stocks and must not be cumulatively summed. Corporate insider purchases, compensation awards, gifts and option exercises must remain distinguishable; transaction date and filing date serve different questions. Public officials' transaction disclosures are not interchangeable with SEC corporate-insider forms, and reported dollar ranges should not become invented exact amounts. Individual donor records require a rights/privacy check: [FEC guidance](https://www.fec.gov/updates/sale-or-use-contributor-information/) restricts certain commercial/solicitation uses. Start with aggregate committee/candidate reporting, not a donor-targeting database.

Prediction markets belong as an optional overlay, not an official forecast. Before plotting an expected rate, preserve the contract's event date, mutually exclusive outcome definitions, resolution rules, prices and timestamps, and liquidity/spread evidence. The result would be an implied rate for a specified future settlement event, not what today's policy rate “should” be. An expectation requires an exhaustive, compatible outcome set with well-defined numeric outcomes; open-ended bins or missing markets cannot silently receive invented representative values. Do not combine unrelated contracts or normalize away material missing probability mass. Historical backfill must come from authentic market history; otherwise begin a clearly dated capture series. Do not revive retired Fed Forecast workflows to obtain it. This overlay is not yet shipped.
