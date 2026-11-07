# M4 source-clock and calendar evidence

Consulted 2026-11-07. These sources justify context, not an automatic regulatory label.

| Primary source | What it supports | What we do not infer |
|---|---|---|
| [BarentsWatch Fish Health guide](https://www.barentswatch.no/veiledning/fiskehelse-forklaring-og-bruksanvisning/) | Farm reports are weekly, generally due the following Tuesday; current-week coverage can be incomplete. Non-reporting can reflect absence of fish or a missing report. | A missing record is not proof of zero lice, closure or sensor failure. |
| [Mattilsynet reporting guidance](https://www.mattilsynet.no/fisk-og-akvakultur/fiskesykdommer/lakselus/veiledning-rapportering-av-lakselus) | Reports include week number, temperature, lice and treatments; they are due the next Tuesday. | There is no measurement hour in our M2/M3 tables. UTC retrieval time is not the reporting clock. |
| [Mattilsynet's spring-window announcement](https://kommunikasjon.ntb.no/pressemelding/14466857/lavere-lakselusgrense-om-varen-og-telling-av-lakselus-i-alle-merder?publisherId=10773547) | The 2017 announcement documents weeks 16-21 in the south and 21-26 in Nordland/Troms/Finnmark. These are meaningful calendar annotations. | We have not reconstructed historical farm-region rules or permits; pooled window summaries are not legal compliance estimates. |
| [Mattilsynet spring counting/enforcement guidance](https://www.mattilsynet.no/fisk-og-akvakultur/fiskesykdommer/lakselus/lavere-lusegrense-om-varen) | Spring counts and enforcement involve sampling uncertainty and sequences of reports. | A single analytical >=0.2 indicator is not an enforcement decision. |
| [BarentsWatch API notice](https://developer.barentswatch.no/docs/fishhealth/) | Published reports can contain inaccuracies and require user quality control. | Cleaned values are not retrospectively certified by the regulator. |

The consulted pages confirm week-based reporting but do not explicitly define ISO 8601.
We retain the M3 ISO-year/week interpretation as a documented display convention and
check calendar validity; all analyses primarily group the stored year/week fields.
Monday positions support ordering, not invented measurement dates. No timezone
conversion is performed on week labels. Coarse periods are four 13-week source-year
blocks, not Gregorian quarters; the final block includes an ISO week 53 if present.
