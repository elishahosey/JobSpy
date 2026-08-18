# JobSpy Scrape Optimization Log

Date: May 25, 2026

## Context

The daily scrape was taking more than 2 hours. The CSV also contained duplicate jobs, which suggested repeated overlap between search terms and job boards.

## Current Diagnosis

The main runtime issue is not CSV writing. The expensive part is the number of network requests.

Each search term is sent to multiple job sites. JobSpy already parallelizes across sites for a single term, but `joblist.py` was running the terms sequentially. The current term set also has natural overlap, so the same job can appear across multiple terms, lanes, and sites.

LinkedIn descriptions must stay enabled because they are useful for downstream filtering and review, but they make LinkedIn slower because description fetching adds extra per-job requests.

## Changes Made

1. Added term-level concurrency.

   `MAX_TERM_WORKERS = 3` lets the script scrape multiple search terms at the same time. This should reduce wall-clock time while keeping concurrency conservative enough to avoid immediately hammering the job boards.

2. Added a per-query cache.

   Scrape results are cached under `.job_cache/` for 12 hours. If the same term, lane, sites, result count, freshness window, and LinkedIn-description setting are requested again, the script reuses cached results instead of scraping them again.

3. Preserved LinkedIn descriptions.

   `LINKEDIN_FETCH_DESCRIPTION = True` remains enabled. The cache key includes this setting, so cached rows without descriptions will not be reused for description-enabled runs.

4. Added pre-scrape duplicate-term skipping.

   Search terms are normalized and checked before creating scrape tasks. If the same term appears in multiple term lists, the script skips repeated scraping for the later lane.

5. Improved output dedupe.

   The final CSV dedupes in multiple passes:

   - `job_url`
   - `id`
   - `title + company + location`

   This helps catch duplicate jobs where the same role appears with different URLs across different sites or searches.

6. Ignored cache files in Git.

   `.job_cache/` was added to `.gitignore` so cached scrape artifacts do not get committed.

## Expected Impact

The biggest expected speedup comes from parallelizing search terms and avoiding repeated scrapes on reruns. The cache should be especially useful when a long scrape fails halfway through or when testing changes in the same day.

LinkedIn will still be one of the slower parts because description fetching remains enabled. If rate limits increase, reduce `MAX_TERM_WORKERS` from `3` to `2` or `1`.

## Next Improvements

1. Add timing logs per term and per site.

   This would show whether Indeed, LinkedIn, Google, or specific terms dominate runtime.

2. Add a durable job identity table.

   Instead of deduping only at the final CSV step, store seen jobs by stable keys such as normalized title, company, location, and canonical URL.

3. Add rate-limit-aware scheduling.

   Use per-site worker limits, exponential backoff, and jitter so one site can slow down without blocking all others.

4. Split scraping from ranking.

   Save raw scrape results first, then run cleaning, prioritization, and ranking as a separate pipeline step.

5. Consider `requests-cache` or a SQLite-backed cache.

   The current cache is simple JSON by query. A request-level cache would be more granular and easier to inspect.

## Resources

- Python `concurrent.futures`: https://docs.python.org/3/library/concurrent.futures.html
- `requests-cache` documentation: https://requests-cache.readthedocs.io/
- urllib3 retry/backoff docs: https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html
- Pandas `drop_duplicates`: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.drop_duplicates.html
- System design deduplication/idempotency overview: https://www.systemdesignsandbox.com/learn/idempotency-deduplication
- Alex Xu, *System Design Interview*: https://www.amazon.com/System-Design-Interview-insiders-Second/dp/B08CMF2CQF

