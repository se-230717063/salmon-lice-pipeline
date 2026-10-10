# Data Sources

## 1. Localities
source_name: BarentsWatch Geodata Localities
provider: BarentsWatch / Mattilsynet
url: https://developer.barentswatch.no/docs/fishhealth
access_method: Public REST/JSON API, OAuth2 client-credentials token required
licence: NLOD (Norwegian Licence for Open Government Data)
terms_notes: Data levert av BarentsWatch og Mattilsynet. (Committed to .gitignore as precaution pending full terms verification).
update_cadence: Weekly
coverage: 2022-2026, active sites across Norway.
record_meaning: one row = metadata for one fish farm locality
join_key: localityNo
first_retrieved: 20261010T181800Z
known_issues: Many passive localities; speed limits undocumented. Pagination handled by cohort x year iteration.

## 2. Average Female Lice
source_name: BarentsWatch Average Female Lice
provider: BarentsWatch / Mattilsynet
url: https://developer.barentswatch.no/docs/fishhealth
access_method: Public REST/JSON API, OAuth2 client-credentials token required
licence: NLOD
terms_notes: Data levert av BarentsWatch og Mattilsynet.
update_cadence: Weekly
coverage: 2022-2026, 40 selected active cohort sites.
record_meaning: one row = one locality's average female lice count for one week
join_key: localityNo, year, week
first_retrieved: 20261010T181800Z
known_issues: 2012-2016 history is sparse; version/revision fields exist; float32 artifacting.

## 3. Sea Temperature
source_name: BarentsWatch Sea Temperature
provider: BarentsWatch / Mattilsynet
url: https://developer.barentswatch.no/docs/fishhealth
access_method: Public REST/JSON API, OAuth2 token required
licence: NLOD
terms_notes: Data levert av BarentsWatch og Mattilsynet.
update_cadence: Weekly
coverage: 2022-2026, 40 selected active cohort sites.
record_meaning: one row = one locality's sea temperature for one week
join_key: localityNo, year, week
first_retrieved: 20261010T181800Z
known_issues: No coordinates provided directly in this endpoint.

## 4. Treatments
source_name: BarentsWatch Lice Treatments
provider: BarentsWatch / Mattilsynet
url: https://developer.barentswatch.no/docs/fishhealth
access_method: Public REST/JSON API, OAuth2 token required
licence: NLOD
terms_notes: Data levert av BarentsWatch og Mattilsynet.
update_cadence: Weekly
coverage: 2022-2026, 40 selected active cohort sites.
record_meaning: one row = one locality's treatments for one week
join_key: localityNo, year, week
first_retrieved: 20261010T181800Z
known_issues: Nested treatment structure (medicinal vs mechanical vs cleaner fish).
