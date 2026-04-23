from jobspy import scrape_jobs

tests = [
    {
        "name": "glassdoor_austin",
        "kwargs": {
            "site_name": ["glassdoor"],
            "search_term": "data engineer",
            "location": "Austin, TX",
            "results_wanted": 10,
        },
    },
    {
        "name": "glassdoor_texas",
        "kwargs": {
            "site_name": ["glassdoor"],
            "search_term": "data engineer",
            "location": "Texas",
            "results_wanted": 10,
        },
    },
    {
        "name": "glassdoor_broad",
        "kwargs": {
            "site_name": ["glassdoor"],
            "search_term": "software engineer",
            "location": "Austin, TX",
            "results_wanted": 10,
        },
    },
]

for test in tests:
    print("\n==============================")
    print(test["name"])
    print("==============================")

    try:
        jobs = scrape_jobs(**test["kwargs"])
        print("count:", len(jobs))

        if not jobs.empty:
            print(jobs[["site", "title", "company", "location", "job_url"]].head(10))
    except Exception as e:
        print("ERROR:", repr(e))