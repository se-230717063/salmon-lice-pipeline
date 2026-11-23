# M5 acquisition contract

The supported project history starts in 2022. The API is queried by locality and
whole year, not by an event-time watermark. Each successful run replays every year
from 2022 through the UTC run clock's year for lice, temperature and treatments,
and refreshes locality metadata. Thus the overlap is the whole project history:
a missed run cannot move a lower bound past uncollected weeks or old corrections.
The last-success checkpoint advances atomically only when all source requests and
required-feed checks succeed. Partial raw responses remain available for replay.

`docs/evidence/m5_delay_profile.json` separates archive age from publication delay.
The original October 10 snapshots re-observed 6,951 lice, 10,440 temperature and 816
treatment keys without an observed revision. The maximum historical age is 1,741
days; it is **not** a measured reporting delay. This short acquisition window
does not establish a safe finite revision window, so a shorter overlap is not
claimed. This conservative choice costs 601 calls per run in 2026. `MAX_REQUESTS=721`
permits 2027 at the current cohort size; an oversized request plan fails before
any partial fetch or checkpoint advance. Requests are sequential, paced by 0.1 s,
with bounded retries and Retry-After handling. The runner caps the entire step.

The provider's [Fish Health documentation](https://developer.barentswatch.no/docs/fishhealth/)
encourages registered batch use but requires a single download thread. Its
[terms](https://www.barentswatch.no/en/articles/api-terms-and-conditions/) require
attribution and warn about high server load. No numeric daily quota or guaranteed
historical retention window was established in the consulted documentation.
The two daily runs at 15:15 and 20:15 Europe/Istanbul are operational polling,
not a claim that the weekly measurements change twice daily. No parallel download
is used. Increase the interval if provider responses indicate throttling.

Source memory is limited to what those annual endpoints still expose. The local
2022-2026 archive proves past availability, not a perpetual retention guarantee.
A failed historical endpoint, unexpected response, or empty required locality/
temperature response fails the run loudly. An overall empty lice feed also fails.
An empty individual lice year or treatment year is permitted: six and 76 such
arrays respectively already exist in the original archive. Source availability
and loss of rows from a formerly nonempty annual response require monitoring;
absence alone is not interpreted as zero lice or no stock.

Limitations: full replay cannot recover a revision no longer exposed by the source,
or infer a deletion when absence has no explicit tombstone semantics. Loading
retains previously observed weekly keys. The archive and independently scheduled
monitor are essential; an HTTP 200 alone does not establish completeness.

Run `python notebooks/profile_m5_delays.py` to refresh the evidence and
`python notebooks/check_m5_ingest.py` for **fixture-only** checkpoint/replay checks.
These tests are not scheduled-run or real missed-run evidence.
