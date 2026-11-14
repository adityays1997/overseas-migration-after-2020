"""Fetch the raw ABS files again, e.g. when a newer release comes out.

usage: python src/download_data.py

The raw files are small (under 3 MB in total), so they're committed to the repo
as well. This script is for refreshing them. If the ABS publishes a new
Overseas Migration release, the folder name and file suffix (2024-25 / 202425)
change, so check the "Data downloads" section of the latest-release page and
update the URLs below.

The Home Affairs BP0019 file has to be downloaded by hand from data.gov.au
(the file name changes every month):
https://data.gov.au/data/dataset/temporary-entrants-visa-holders
Save it in data/raw/home_affairs_bp0019/ and update BP0019_FILE in
prepare_data.py.
"""

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "abs_overseas_migration_2024_25/34070DO004_202425.xlsx":
        "https://www.abs.gov.au/statistics/people/population/overseas-migration/2024-25/34070DO004_202425.xlsx",
    "abs_population_mar_2026/310102.xlsx":
        "https://www.abs.gov.au/statistics/people/population/national-state-and-territory-population/mar-2026/310102.xlsx",
    "abs_population_mar_2026/310104.xlsx":
        "https://www.abs.gov.au/statistics/people/population/national-state-and-territory-population/mar-2026/310104.xlsx",
}


def main():
    for rel, url in FILES.items():
        dest = ROOT / "data" / "raw" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        # The ABS site sometimes rejects requests without a browser-like user agent.
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            dest.write_bytes(resp.read())
        print(f"saved {rel} ({dest.stat().st_size / 1024:,.0f} KB)")


if __name__ == "__main__":
    main()
