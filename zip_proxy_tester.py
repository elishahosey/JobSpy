from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests
import tls_client

from jobspy.ziprecruiter.constant import get_cookie_data, headers
from jobspy.ziprecruiter.util import add_params
from jobspy.model import ScraperInput, Site


ZIP_API_URL = "https://api.ziprecruiter.com/jobs-app/jobs"
ZIP_EVENT_URL = "https://api.ziprecruiter.com/jobs-app/event"
IPIFY_URL = "https://api.ipify.org"


@dataclass
class ProxyRecord:
    host: str
    port: str
    username: str
    password: str
    source_line: int

    @property
    def proxy_url(self) -> str:
        return f"http://{self.username}:{self.password}@{self.host}:{self.port}"

    @property
    def label(self) -> str:
        return f"{self.host}:{self.port}:{self.username}"


def parse_proxy_line(line: str, line_number: int) -> ProxyRecord | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    if "://" in line:
        scheme, rest = line.split("://", 1)
        if "@" not in rest:
            raise ValueError(f"Line {line_number}: URL proxy is missing credentials")
        creds, host_port = rest.rsplit("@", 1)
        username, password = creds.split(":", 1)
        host, port = host_port.rsplit(":", 1)
        return ProxyRecord(host, port, username, password, line_number)

    parts = line.split(":")
    if len(parts) != 4:
        raise ValueError(
            f"Line {line_number}: expected host:port:username:password format"
        )
    host, port, username, password = parts
    return ProxyRecord(host, port, username, password, line_number)


def load_proxies(path: Path) -> list[ProxyRecord]:
    records: list[ProxyRecord] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        record = parse_proxy_line(line, line_number)
        if record:
            records.append(record)
    return records


def get_exit_ip(proxy: ProxyRecord, timeout: int) -> tuple[str | None, str | None]:
    proxy_dict = {"http": proxy.proxy_url, "https": proxy.proxy_url}
    try:
        response = requests.get(IPIFY_URL, proxies=proxy_dict, timeout=timeout)
        response.raise_for_status()
        return response.text.strip(), None
    except Exception as exc:
        return None, repr(exc)


def test_ziprecruiter(
    proxy: ProxyRecord,
    *,
    search_term: str,
    location: str,
    timeout: int,
    client_identifier: str,
) -> dict[str, object]:
    session = tls_client.Session(
        client_identifier=client_identifier,
        random_tls_extension_order=True,
    )
    session.proxies = {"http": proxy.proxy_url, "https": proxy.proxy_url}
    session.headers.update(headers)

    try:
        event_response = session.post(ZIP_EVENT_URL, data=get_cookie_data)
    except Exception as exc:
        return {
            "zip_pass": False,
            "zip_stage": "event",
            "zip_error": repr(exc),
        }

    scraper_input = ScraperInput(
        site_type=[Site.ZIP_RECRUITER],
        search_term=search_term,
        location=location,
        results_wanted=1,
    )
    params = add_params(scraper_input)

    try:
        response = session.get(ZIP_API_URL, params=params, timeout_seconds=timeout)
    except Exception as exc:
        return {
            "zip_pass": False,
            "zip_stage": "jobs",
            "zip_event_status": event_response.status_code,
            "zip_error": repr(exc),
        }

    error_code = ""
    error_message = ""
    job_count = 0
    body_preview = response.text[:300].replace("\n", " ")

    try:
        payload = response.json()
        error_code = payload.get("error_code", "")
        error_message = payload.get("error_message", "")
        job_count = len(payload.get("jobs") or [])
    except json.JSONDecodeError:
        pass

    return {
        "zip_pass": response.status_code in range(200, 400) and job_count > 0,
        "zip_stage": "jobs",
        "zip_event_status": event_response.status_code,
        "zip_status": response.status_code,
        "zip_error_code": error_code,
        "zip_error_message": error_message,
        "zip_job_count": job_count,
        "zip_body_preview": body_preview,
    }


def build_output_path(input_path: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg)
    return input_path.with_name(f"{input_path.stem}_zip_results.csv")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test Webshare proxies against ZipRecruiter and write a CSV."
    )
    parser.add_argument("input", help="Proxy list file, one proxy per line.")
    parser.add_argument("-o", "--output", help="Output CSV path.")
    parser.add_argument("--limit", type=int, help="Only test the first N proxies.")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between tests.")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout seconds.")
    parser.add_argument("--search-term", default="sql")
    parser.add_argument("--location", default="Texas")
    parser.add_argument("--client-identifier", default="chrome_120")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = build_output_path(input_path, args.output)
    proxies = load_proxies(input_path)
    if args.limit:
        proxies = proxies[: args.limit]

    fieldnames = [
        "source_line",
        "proxy_label",
        "exit_ip",
        "ip_error",
        "zip_pass",
        "zip_stage",
        "zip_event_status",
        "zip_status",
        "zip_error_code",
        "zip_error_message",
        "zip_job_count",
        "zip_error",
        "zip_body_preview",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()

        for index, proxy in enumerate(proxies, start=1):
            print(f"[{index}/{len(proxies)}] testing {proxy.label} ...", flush=True)
            exit_ip, ip_error = get_exit_ip(proxy, args.timeout)
            zip_result = test_ziprecruiter(
                proxy,
                search_term=args.search_term,
                location=args.location,
                timeout=args.timeout,
                client_identifier=args.client_identifier,
            )

            row = {
                "source_line": proxy.source_line,
                "proxy_label": proxy.label,
                "exit_ip": exit_ip or "",
                "ip_error": ip_error or "",
                **zip_result,
            }
            writer.writerow({field: row.get(field, "") for field in fieldnames})
            output_file.flush()

            status = "PASS" if zip_result.get("zip_pass") else "FAIL"
            error_code = zip_result.get("zip_error_code") or zip_result.get("zip_error")
            print(f"    {status} exit_ip={exit_ip or 'n/a'} {error_code or ''}")

            if index < len(proxies) and args.delay:
                time.sleep(args.delay)

    print(f"Done. Wrote {output_path}")


if __name__ == "__main__":
    main()
