# Data Sources

source_name: BarentsWatch Fish Health API
provider: BarentsWatch / Mattilsynet
url: https://developer.barentswatch.no/docs/fishhealth
access_method: Public REST/JSON API, OAuth2 client-credentials token required
licence: NLOD
terms_notes: Data levert av BarentsWatch og Mattilsynet. Redistribution is permitted.
update_cadence: Weekly
coverage: 2022-2026, ~150,000 weekly records across Norway's active sites.
record_meaning: one row = one locality's lice/temperature/treatment data for one week
join_key: localityNo, year, week
first_retrieved: [To be filled after first successful run]
known_issues: Data resolution is weekly. Fallow periods create non-reporting gaps. Undocumented API rate limits may constrain batch ingestion.
