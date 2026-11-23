# Cagatay M5 implementation evidence

The runner, Windows task, acquisition replay, clock propagation and offline
rebuild checks are implemented. This document records implementation evidence,
not seven days of scheduled operation.

- Runner acceptance: `docs/evidence/m5_runner_checks.json`.
- Acquisition fixtures: `docs/evidence/m5_ingest_checks.json`; not live evidence.
- Delay/archive-age distinction: `docs/m5_ingest_design.md` and its JSON profile.
- Two real offline runner builds with one clock: `docs/evidence/m5_rebuild_checks.json`.
  All 17 table digests match, and the M4 notebook executes with six figures and
  no database changes. Original production tables were untouched by these tests.
- Full raw replay currently takes about 3.7 seconds locally (see measured evidence).
  At linear scaling, 100 times the current archive could take roughly six minutes;
  this is an estimate, not a benchmark. Revisit full reload when measured times
  approach the 30-minute step budget or the schedule interval.

## Validation decisions

M3 STOP checks are retained and all deliberate STOP injections still fail.
Freshness uses the explicit UTC run clock, not the latest acquisition timestamp.
The tolerated age is 21 days from a weekly period's Monday: weekly period width,
publication delay and one additional reporting week. Independent monitoring will
make stale entities visible even when a build itself succeeds.
Both lice and temperature are checked; future values are also checked against
the supplied run clock, not only the source snapshot date.

Historical missingness, retained spike/stuck flags, non-identifying substance code
0 and unknown cage counts are deliberately INFO: they are reviewed analytical
limitations already documented in the M3 report, not new recurring operational
incidents. Values and quality flags are not erased. Unknown stock/reporting
obligation also makes exact previous-week coverage an INFO inventory.

Volume is the sum of net new raw table keys, with the typical positive scheduled
run estimated from up to 30 earlier load summaries. Ten times typical is WARN.
The current run and empty-database bootstrap loads are excluded from this baseline.
Zero growth is normally WARN if freshness is bad, but deliberately INFO while the
weekly source is fresh: two polls a day often see no new weekly keys. This explicit
downgrade avoids a permanent zero-volume WARN while the separate freshness checks
still expose a stopped feed. Revisions at existing keys are not called new rows.

Loading a revised treatment list removes dependent clean event rows within the
same source-load transaction before replacing event keys. The immediately following
clean rebuild restores the derived layer. A failed load rolls back both changes;
a failed clean is recorded, stops the runner and leaves the last committed source
layer and rolled-back clean layer for diagnosis. There is no claim of one transaction
spanning all four separate processes.

## Review regressions

`python notebooks/check_m5_review.py` verifies nine cases: fresh weekly zero
growth is INFO, both feed clocks can become stale, future values cause STOP,
missing raw sources fail without changing existing rows, the volume baseline
excludes the current run and bootstrap, tenfold volume warns, a late treatment
revision failure restores both layers, and successful list replacement removes
obsolete event keys without breaking foreign keys, and Monday's coverage target
allows the preceding week's Tuesday reporting deadline. See
`docs/evidence/m5_review_checks.json`.

Raw JSON publication uses a private `.part` file and an atomic exclusive link.
A crash cannot expose a truncated `.json` for loading. Fixture checks verify
cleanup after a failed publish. A source's valid empty annual lice/treatment
array remains distinct from a missing source directory or empty required feed.

## Live review on November 23

The real manual run `1a30ea7b5e4b4526b752ede762b5c5e0` completed all four steps
with exit code 0: 601 source requests returned HTTP 200. Ingestion took 627 seconds,
loading 5 seconds and cleaning 1 second, for 633 seconds total. The archive now
contains 1,805 JSON files. This is manual evidence and is **not** a scheduled day.
`docs/evidence/m5_live_review.json` exports the real run and post-review validation.

The updated archive also passes two offline runner builds with identical 17-table
hashes and a real M4 notebook execution with six figures and unchanged DB contents.

Two freshness WARNs remain, covering the same 15 farms in lice and temperature.
All source requests succeeded, but recent measurements are absent for those farms.
The registry endpoint does not expose stock/production status, so inactivity cannot
be asserted. This is an unresolved operational interpretation, not an authentication
failure. Do not widen the age threshold or silence these checks merely to obtain
green output. Before final M5 submission, investigate the reporting expectation or
document a justified classification; the current code does not claim every feed
entity is fresh or that M5's no-permanent-WARN requirement is fully satisfied.

## Operations to complete

Monitor, its independent task, six drill documentation and the real missed-start
experiment belong to Egemen's next stage. No real missed-start recovery has yet
been demonstrated. Confirm the actual 15:15/20:15 scheduled results before claiming
scheduled operational success. Task XML is an
export of the registered Windows S4U task; wake timers depend on machine support.
After power loss, inspect a leftover lock and its PID before removing it; do not
automatically steal a lock that may belong to a still-running writer.

The `m3` and `m4` tags are preserved. No `m5` tag has been created.
