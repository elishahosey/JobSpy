# Normal scrape configuration

Edit `config/searches.json`, then run from the repository root:

```powershell
.\.venv-jobspy\Scripts\python.exe -m jobspy.batch config/searches.json output/jobs.csv
```

The CLI inserts today's date as `MM-DD-YYYY` before the extension. The command
above writes `output/jobs-MM-DD-YYYY.csv`; an `.xlsx` argument writes the same
date pattern with an Excel extension. If the supplied name already ends in
that date pattern, it is not duplicated. For Excel, install `openpyxl` in that
same environment. Each invocation scrapes again. To export both formats from the
same results, load the JSON and call `scrape_batch()` once, then use pandas'
`to_csv()` and `to_excel()` methods. Use distinct filenames to retain past runs.

## Migration source and active settings

Source: `custom-job-search-workflow:joblist.py` at commit
`6cc4eae515599ad56dbe16e04b8bdc9f4de4b121`. The source was parsed and inspected;
it was not imported or executed. Neither the old branch nor its scripts are
merged. No `joblist.py` wrapper is needed: the module command is the entry point.

The saved switches were `ANALYZE_MODE=False`, `FALLBACK=False`,
`CONTRACT_ONLY=False`, `ZIPRECRUITER_ONLY=False`, `QUALIFICATION_SEARCH=True`.
The active order was core, qualification, then secondary queries.

| Setting | Migrated value |
| --- | --- |
| Active searches | 20 core + 88 qualification + 19 additional secondary = 127 |
| Providers | `indeed`, `linkedin`, `google` |
| Location | `Texas`, as used by the old script; not the Houston demo |
| Country | `USA` |
| Age filter | `hours_old: 24` |
| Core result limit | `results_wanted: 120` per query per provider |
| Qualification/secondary limit | shared `results_wanted: 1` per query per provider |
| Description fetching | `fetch_description: true`, replacing the deprecated LinkedIn alias |
| Remote filter | `is_remote: false`, the old call's upstream default |
| Proxies | `null`, matching the active old setting |
| Term concurrency | sequential, matching `MAX_TERM_WORKERS=1` |
| Google query | exact old `"<term> jobs since the past 1 days in Texas"` override per entry |

Other unpassed scraper filters continue to use upstream defaults. Historical
commented proxy settings and credentials were not copied.

This is the historical full run, **not a 100-row or smoke configuration**.
It requests 2,507 results per provider in aggregate (20 x 120 + 107 x 1),
or nominally 7,521 across three providers, before provider limits and empty
results. Actual counts vary; duplicates are retained. For a smaller run, reduce
the query list and limits in a copy. **A per-query `results_wanted` overrides
the shared value**: changing only the shared value does not reduce core queries.
The output filename never controls the count.

Google overrides include their own location and time text. Changing shared
`location` or `hours_old` does not rewrite those explicit strings. Edit the
overrides too, or remove them to use upstream's generated Google queries.
Google returned the known missing-cursor warning during earlier live checks;
do not interpret an empty Google result as a definitive absence of matching jobs.

## Deliberate mode assignments

The JSON stores literal, manually reviewed labels; the runner never infers a
mode from words. There are **22 `job_title`, 89 `skill_based`, and 16 `mixed`**
queries in the initial migration. Exact spelling and capitalization are retained.

- Core role names and the eight secondary role names are `job_title`.
  `sql developer`, `etl engineer`, `etl developer`, `api integration engineer`,
  `etl integration engineer`, `data integration engineer`, and
  `backend data engineer` are treated as established specialized titles, even
  though they contain technology/domain words.
- All 88 qualification queries are `skill_based`: their source intent was to
  find capabilities, tools, education, and work activities, rather than named
  roles. This includes ambiguous activity phrases such as `production support
  sql`, `data science sql python`, `release confidence testing`, and
  `multi environment deployment`. Core `sql etl` is also `skill_based`.
- The following role-plus-skill/domain phrases are `mixed`. Some could be read
  as specialized titles; the chosen interpretation preserves the old search
  text while making the additional keyword intent explicit:

| Query | Reason for `mixed` |
| --- | --- |
| `data analyst sql` | role plus SQL |
| `systems integration engineer data` | role plus data emphasis |
| `software engineer data engineering` | role plus domain |
| `interface engineer data` | role plus data emphasis |
| `middleware engineer data` | role plus data emphasis |
| `forward deployed engineer sql` | role plus SQL |
| `forward deployed engineer data` | role plus data emphasis |
| `forward deployed software engineer integration` | role plus integration emphasis |
| `forward deployed engineer api` | role plus API |
| `backend engineer data` | role plus data emphasis |
| `software engineer data` | role plus data emphasis |
| `backend software engineer sql` | role plus SQL |
| `software engineer integration` | role plus integration emphasis |
| `Data Warehouse Analyst SQL` | role plus SQL |
| `Analytics Engineer SQL` | role plus SQL |
| `systems analyst sql etl data integration` | role plus skills/domain |

`api integration engineer` also appeared in the secondary list, but the old
task builder already skipped it there after scheduling it in core. The config
therefore represents it once, with its original effective core limit of 120.
This is a one-time reconstruction of the active query list, not runtime query
or job deduplication. If you add repeated entries, the batch runner executes
each and retains every returned row with its origin.

## Intentionally not migrated

- Inactive market-analysis, contract-only, bridge/survival fallback, and
  ZipRecruiter-only query sets and rotation settings.
- The custom cache, retry orchestration, progress-logging implementation, and
  old flags. The new path is the existing sequential batch runner, using
  upstream provider behavior and logs. Each run makes fresh requests; upstream
  exceptions propagate, so partial export/retry behavior differs from the old
  custom runner.
- Post-scrape deduplication, review priorities, sorting by those priorities,
  cleaning, grading, and downstream handoff scripts. Raw results preserve all
  returned rows and their `search_query` / `search_mode` provenance.

The old implementation remains available only on its original branch. This
configuration, not that script, is now the maintained scrape setup. The small
`examples/searches.json` stays available as a demo with different settings.

## Migration validation (October 1, 2026)

All 18 offline tests passed, including execution of this real config through
both CSV and Excel CLI exports with mocked providers. The migration audit
compared all 127 query strings and their order with the old active configuration,
checked the per-query limits, and verified shared options and Google overrides.

A temporary copy selected `data engineer` (job_title), `sql etl` (skill_based),
and `data analyst sql` (mixed), with all result limits reduced to one. Texas,
the 24-hour filter, and description fetching were retained. LinkedIn and Indeed
each returned one job for each query: six rows with correct provenance. Google
was tested separately with the preserved query overrides and returned the known
missing-cursor warning and zero rows. Live Google retrieval remains unverified.

The local pandas 2.3.3 installation emitted a non-failing FutureWarning about
concatenating all-NA columns during the live CSV export. No rows or provenance
were lost. Source behavior remains unchanged apart from the per-query result
limit option. Review your full-run limits before starting: this config deliberately
preserves the old larger workload.
