from jobspy import scrape_jobs
import requests


proxy = "http://kyepxfcr-US-rotate:6tt6cwkm0mkn@p.webshare.io:80"
#
tests = [
    # {
    #     "name": "basic_city",
    #     "kwargs": {
    #         "site_name": ["zip_recruiter"],
    #         "search_term": "data engineer",
    #         "proxies": [proxy],
    #         "location": "Austin, TX",
    #         "results_wanted": 10,
    #     },
    # },
    {
        "name": "basic_state",
        "kwargs": {
            "site_name": ["zip_recruiter"],
            "search_term": "sql",
            "proxies": [proxy],
            "location": "Texas",
            "results_wanted": 1,
        },
    },
    # {
    #     "name": "remote",
    #     "kwargs": {
    #         "site_name": ["zip_recruiter"],
    #         "search_term": "data engineer",
    #         "location": "United States",
    #         "proxies": [proxy],
    #         "results_wanted": 10,
    #         "is_remote": True,
    #     },
    # },
    # {
    #     "name": "broad_term",
    #     "kwargs": {
    #         "site_name": ["zip_recruiter"],
    #         "search_term": "software engineer",
    #         "proxies": [proxy],
    #         "location": "Austin, TX",
    #         "results_wanted": 10,
    #     },
    # },
    # {
    #     "name": "with_user_agent",
    #     "kwargs": {
    #         "site_name": ["zip_recruiter"],
    #         "search_term": "data engineer",
    #         "location": "Austin, TX",
    #         "proxies": [proxy],
    #         "results_wanted": 10,
    #         "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    #     },
    # },
]

#Testing proxy connectivity
print(requests.get(
    "https://api.ipify.org",
    proxies={"http": proxy, "https": proxy},
    timeout=20,
).text)


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