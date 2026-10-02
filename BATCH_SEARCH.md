# Batch searches and exports

`jobspy.batch` runs ordinary `scrape_jobs()` calls sequentially, adds query
metadata, and concatenates their dataframes. Title, skill, and mixed searches
use the same provider search mechanism. No scraper internals are changed.

## Run a small batch

From the repository root in PowerShell:

```powershell
git switch codex/sync-upstream-search-update
python -m venv venv
.\venv\Scripts\python.exe -m pip install -e .
.\venv\Scripts\python.exe -m jobspy.batch examples/searches.json output/jobs-test.csv
```

Edit `examples/searches.json` before running. Its five searches cover all three
modes. `scrape_options` contains ordinary `scrape_jobs()` arguments shared by
every search: providers, location, result count, age, remote filter, etc.
Houston is only an editable example location; the batch code has no default
location. The example requests two results per provider per query, roughly
20 rows at most from LinkedIn and Indeed. For roughly 100 returned rows, set
`results_wanted` to 10 (5 queries x 2 providers x 10). This is not a promise of
100 distinct jobs: providers may return fewer jobs and overlapping results
are intentional.

```json
{
  "searches": [
    {"query": "Data Engineer", "mode": "job_title"},
    {"query": "SQL ETL Python", "mode": "skill_based"},
    {"query": "Backend Engineer SQL API", "mode": "mixed"}
  ],
  "scrape_options": {
    "site_name": ["linkedin", "indeed"],
    "location": "Austin, TX",
    "results_wanted": 2
  }
}
```

`query` is passed unchanged as `search_term`; `mode` is metadata only and must
be `job_title`, `skill_based`, or `mixed`. Keep `search_term` and
`google_search_term` out of shared `scrape_options` to avoid ambiguous origins.
Each search may optionally contain its own `google_search_term`.

## Dataframe and export behavior

```python
from jobspy.batch import scrape_batch

jobs = scrape_batch(
    [
        {"query": "Data Engineer", "mode": "job_title"},
        {"query": "SQL ETL Python", "mode": "skill_based"},
    ],
    site_name=["linkedin", "indeed"],
    location="Austin, TX",
    results_wanted=2,
)
jobs.to_csv("jobs.csv", index=False)
# Optional: install openpyxl, then jobs.to_excel("jobs.xlsx", index=False)
```

Every returned row retains its original JobSpy fields, including the provider
`id`, plus `search_query` and `search_mode`. Query text, including quotes and
whitespace, is preserved. The wrapper does not deduplicate within or across
returned dataframes. Repeated searches and repeated function calls retain all
returned rows; there is no persistent seen-job state. Providers' existing
deduplication within a single scrape is unchanged. IDs such as `li-...`,
`in-...`, and `go-...` are preserved without canonicalization.

CSV and Excel remain standard pandas exports with two additional columns.
An entirely empty batch result still exports the normal JobSpy column headers
and the two metadata headers. Empty searches create no synthetic job rows.
Exceptions propagate; the CLI does not write a partial export after a raised
provider exception. Some upstream providers log an error and return an empty
or partial dataframe instead: check provider logs as well as row counts.

For Excel:

```powershell
.\venv\Scripts\python.exe -m pip install openpyxl
.\venv\Scripts\python.exe -m jobspy.batch examples/searches.json output/jobs-test.xlsx
```

Each CLI invocation performs a fresh scrape. Use the dataframe API to write
CSV and Excel from the same results without scraping twice. Output paths are
overwritten as with pandas; use a new filename for each execution if keeping
all raw runs. There is no append, merge, or deduplication step. Excel's normal
cell-length and row limits still apply, so CSV is preferable for full, long
job descriptions.

## Provider behavior verified against upstream

Inspection baseline: `10b5417c8f2c99a6159733cf0f52a06c96c3832d` (1.1.82).

- `scrape_jobs()` and `ScraperInput` accept one string for `search_term`, not a
  list of queries. Multiple sites are supported, but there is no batch-query
  API or built-in query-origin export metadata.
- LinkedIn maps the string directly to its `keywords` request parameter.
  Skill strings use the same path as titles; matching is controlled by LinkedIn.
- Indeed sends the string as GraphQL `what`, escaping quotes for transport.
  Upstream's README describes title and description matching, quoted phrases,
  exclusions, and OR syntax. The wrapper preserves that syntax and does not
  promise any particular provider ranking or match semantics.
- Google builds a query from `search_term`, job type, location, age, and remote
  options. A nonempty `google_search_term` replaces that entire generated query.
  This code behavior is broader than the upstream README's Google guidance.
  Put any needed location or time constraint into an explicit Google query.

For Google, add `"google"` to `site_name`. Either leave the override out to use
upstream's generated query, or supply it per search:

```json
{
  "query": "SQL ETL Python",
  "mode": "skill_based",
  "google_search_term": "SQL ETL Python jobs near Austin, TX since yesterday"
}
```

The override is sent only through the existing `google_search_term` argument.
`search_query` remains the exact configured `query` on all rows, so retain the
JSON config alongside exports when using Google overrides. Google syntax and
availability can require manual checking in Google Jobs. No query DSL is added.

## Offline tests

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests mock provider calls, exercise metadata and duplicates, verify the
single-query schema and provider request construction, and round-trip CSV and
Excel. The Excel test skips if `openpyxl` is not installed. No test contacts a
job board. Run small live batches separately and distinguish provider blocks,
rate limits, or empty results from offline test correctness.

The upstream revision has no tracked tests or type-check configuration. Its CI
builds a wheel, installs it, and checks import. The pinned Black 24.2.0 hook
already reports 10 upstream files requiring formatting; this branch leaves
those files unchanged. Format-check only the added Python files with:

```powershell
.\venv\Scripts\python.exe -m pip install black==24.2.0
.\venv\Scripts\python.exe -m black --check jobspy/batch.py tests/test_batch.py
```

## Validation record (October 1, 2026)

- Sync: fast-forwarded from `fda080a373e8226f3fd60635323f5da9af9892b1` to
  `10b5417c8f2c99a6159733cf0f52a06c96c3832d`, without conflicts. Fork main
  stayed at the former SHA. No custom workflow commits were brought over.
- Windows / Python 3.12.0: upstream wheel build, binary dependency installation,
  installed-package import, and `pip check` passed. Baseline unittest discovery
  reported zero tests, not a passing upstream test suite.
- All 13 new offline tests passed, including CSV and Excel round trips with
  openpyxl 3.1.5. Added files pass Black 24.2.0; upstream's 10 existing formatting
  failures remain. No type checker is configured.
- Final wheel build, installation, and installed batch CLI import/help passed.
  Runtime verification used pandas 3.0.6, pydantic 2.13.5, and curl_cffi 0.16.3;
  other supported Python/dependency combinations were not exercised locally.
- Live smoke tests used configurable location `Houston, TX`, `hours_old=168`,
  and `results_wanted=1`. LinkedIn and Indeed each returned one row for each of
  `Data Engineer`, `SQL ETL Python`, and `Backend Engineer SQL API`. All six
  rows had the expected query and mode metadata.
- Google was tested separately with each query followed by
  `jobs near Houston, TX in the last week` as `google_search_term`. All three
  returned zero rows and the upstream warning `initial cursor not found`.
  No explicit rate-limit response was reported. This does not establish whether
  the cause was provider blocking, query matching, or upstream parsing. Google
  request construction passes offline checks; live Google retrieval remains
  unverified and should be checked manually before relying on it.

Before merging, review a small raw export, verify any Google syntax in Google
Jobs, and test your intended filters and result counts. Upstream now requires
Python >=3.10, pandas >=2.1.2, and curl_cffi >=0.16.2 (replacing tls-client).
Use a fresh environment or update dependencies; the old custom workflow and
its environment were deliberately left alone.
