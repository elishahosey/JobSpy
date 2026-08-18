"""
Merge all CSV files in archive_cleaned into one CSV.

Default output:
    archive_cleaned_merged.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


DEFAULT_INPUT_DIR = Path("archive_cleaned")
DEFAULT_OUTPUT_FILE = Path("archive_cleaned_merged.csv")
CSV_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def natural_key(path: Path) -> list[int | str]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def find_csv_files(input_dir: Path, output_file: Path) -> list[Path]:
    output_file = output_file.resolve()
    return [
        path
        for path in sorted(input_dir.glob("*.csv"), key=natural_key)
        if path.resolve() != output_file
    ]


def read_csv_rows(csv_file: Path) -> tuple[list[str], list[dict[str, str]], str]:
    last_error: UnicodeDecodeError | None = None

    for encoding in CSV_ENCODINGS:
        try:
            with csv_file.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                return reader.fieldnames or [], list(reader), encoding
        except UnicodeDecodeError as error:
            last_error = error

    if last_error:
        raise last_error

    return [], [], CSV_ENCODINGS[0]


def merge_csv_files(
    input_dir: Path,
    output_file: Path,
    add_source_file: bool = False,
    drop_duplicates: bool = False,
) -> None:
    csv_files = find_csv_files(input_dir, output_file)
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {input_dir}")

    fieldnames: list[str] = []
    files_with_rows: list[tuple[Path, list[dict[str, str]]]] = []
    total_rows = 0

    for csv_file in csv_files:
        file_fieldnames, rows, encoding = read_csv_rows(csv_file)
        for fieldname in file_fieldnames:
            if fieldname not in fieldnames:
                fieldnames.append(fieldname)

        files_with_rows.append((csv_file, rows))
        total_rows += len(rows)
        print(f"Found {len(rows):,} rows in {csv_file} ({encoding})")

    if add_source_file and "source_file" not in fieldnames:
        fieldnames.insert(0, "source_file")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_rows = 0
    duplicate_rows = 0
    seen_rows: set[tuple[str, ...]] = set()

    with output_file.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for csv_file, rows in files_with_rows:
            for row in rows:
                if add_source_file:
                    row["source_file"] = csv_file.name

                row_key = tuple(row.get(fieldname, "") for fieldname in fieldnames)
                if drop_duplicates and row_key in seen_rows:
                    duplicate_rows += 1
                    continue

                seen_rows.add(row_key)
                writer.writerow(row)
                output_rows += 1

    if drop_duplicates:
        print(f"Dropped {duplicate_rows:,} duplicate rows")

    print()
    print(f"Merged {len(csv_files):,} CSV files")
    print(f"Input rows: {total_rows:,}")
    print(f"Output rows: {output_rows:,}")
    print(f"Wrote: {output_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge all CSV files from archive_cleaned into one CSV."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Folder containing CSV files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Merged CSV path. Default: {DEFAULT_OUTPUT_FILE}",
    )
    parser.add_argument(
        "--add-source-file",
        action="store_true",
        help="Add a source_file column showing which CSV each row came from.",
    )
    parser.add_argument(
        "--drop-duplicates",
        action="store_true",
        help="Drop exact duplicate rows after merging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    merge_csv_files(
        input_dir=args.input_dir,
        output_file=args.output_file,
        add_source_file=args.add_source_file,
        drop_duplicates=args.drop_duplicates,
    )


if __name__ == "__main__":
    main()
