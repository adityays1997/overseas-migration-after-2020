"""Turn the raw ABS and Home Affairs workbooks into tidy CSVs in data/processed.

Run from the repo root:  python src/prepare_data.py

Nothing in data/raw is modified. Every step that drops or reshapes rows prints
a line, and those lines are what cleaning_log.md is built from.
"""

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

VISA_FILE = RAW / "abs_overseas_migration_2024_25" / "34070DO004_202425.xlsx"
COMPONENTS_FILE = RAW / "abs_population_mar_2026" / "310102.xlsx"
ERP_FILE = RAW / "abs_population_mar_2026" / "310104.xlsx"
BP0019_FILE = RAW / "home_affairs_bp0019" / "bp0019l-number-of-temporary-visa-holders-in-australia-at-2026-09-30-v100.xlsx"

STATE_ABBR = {
    "New South Wales": "NSW", "Victoria": "Vic", "Queensland": "Qld",
    "South Australia": "SA", "Western Australia": "WA", "Tasmania": "Tas",
    "Northern Territory": "NT", "Australian Capital Territory": "ACT",
    "Australia": "Aus",
}

log_lines = []


def log(msg):
    log_lines.append(msg)
    print(msg)


# ---------------------------------------------------------------------------
# ABS Overseas Migration, data cube 4 (visa groups by state, financial years)
# ---------------------------------------------------------------------------

def _clean_label(text):
    # Labels carry footnote markers like "Total(i)" or "2024-25(g)".
    return re.sub(r"\([a-z]\)", "", str(text)).strip()


def read_visa_cube(path=VISA_FILE):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    records = []
    for sheet in wb.sheetnames:
        if not sheet.startswith("Table"):
            continue
        rows = list(wb[sheet].iter_rows(values_only=True))

        # Table 4.1 (Australia) has one more footnote than the state tables,
        # so the header row isn't in a fixed place. Find it by its first cell.
        header_idx = next(i for i, r in enumerate(rows) if r[0] == "Direction")
        title = rows[header_idx - 1][0]
        state = re.search(r"groups, (.+?), 2004-05", title).group(1)
        years = [_clean_label(y) for y in rows[header_idx][3:]]

        direction = group = None
        for r in rows[header_idx + 1:]:
            if r[0] and str(r[0]).startswith("©"):
                break
            if all(c is None for c in r):
                continue
            if r[0]:
                direction = "arrivals" if "arrivals" in r[0] else "departures"
            if r[1]:
                group = _clean_label(r[1])
            item = _clean_label(r[2]) if r[2] else group
            for fy, value in zip(years, r[3:]):
                records.append({
                    "state": state, "direction": direction,
                    "group": group, "item": item,
                    "fy": fy, "persons": value,
                })
    df = pd.DataFrame(records)
    log(f"visa cube: read {wb.sheetnames.__len__() - 1} tables, {len(df):,} cells in long form")
    return df


def tidy_visa_cube(raw):
    """Map the ABS row labels onto one flat set of visa groups.

    The student rows are tricky: 'Student' is already the sum of the three
    'Student - ...' rows below it, so keeping all four would double count.
    I keep the three sector rows for the student drill-down in a separate
    column and use the 'Student' row for group totals.
    """
    df = raw.copy()
    df["persons"] = pd.to_numeric(df["persons"])

    item_map = {
        "Family": ("Permanent", "Family"),
        "Skilled (permanent)": ("Permanent", "Skilled (permanent)"),
        "Special eligibility & humanitarian": ("Permanent", "Humanitarian & special eligibility"),
        "Other (permanent)": ("Permanent", "Other permanent"),
        "Student": ("Temporary", "Student"),
        "Skilled (temporary)": ("Temporary", "Skilled (temporary)"),
        "Working holiday": ("Temporary", "Working holiday"),
        "Visitors": ("Temporary", "Visitor"),
        "Other (temporary)": ("Temporary", "Other temporary"),
        "New Zealand citizens (subclass 444)": ("NZ citizen", "NZ citizen (444)"),
        "Australian citizens (no visa)": ("Australian citizen", "Australian citizen"),
    }
    totals = {"Total permanent visas", "Total temporary visas", "Total"}
    sectors = {"Student - vocational education and training",
               "Student - higher education", "Student - other"}

    detail = df[df["item"].isin(item_map)].copy()
    detail[["visa_type", "visa_group"]] = detail["item"].map(item_map).apply(pd.Series)
    log(f"visa cube: kept {len(detail):,} cells for the 11 main visa/citizenship groups")
    log(f"visa cube: set aside {df['item'].isin(totals).sum():,} subtotal/total cells (used only for checks)")
    log(f"visa cube: set aside {df['item'].isin(sectors).sum():,} student-sector cells (subset of 'Student'; kept in student_sectors.csv)")

    # 'Total' includes visa-unknown travellers, which have no row of their own.
    # Back them out so the groups add up to the published total.
    tot = (df[df["item"] == "Total"]
           .set_index(["state", "direction", "fy"])["persons"])
    parts = detail.groupby(["state", "direction", "fy"])["persons"].sum()
    unknown = (tot - parts).rename("persons").reset_index()
    unknown["item"] = "Unknown visa (derived)"
    unknown["visa_type"] = "Unknown"
    unknown["visa_group"] = "Unknown visa"
    log(f"visa cube: derived {len(unknown):,} 'unknown visa' cells as Total minus the 11 groups "
        f"(range {unknown['persons'].min():,.0f} to {unknown['persons'].max():,.0f} persons)")

    keep = ["state", "direction", "visa_type", "visa_group", "fy", "persons"]
    long = pd.concat([detail[keep], unknown[keep]], ignore_index=True)
    long["state_abbr"] = long["state"].map(STATE_ABBR)
    long["fy_end"] = long["fy"].str[:4].astype(int) + 1

    wide = long.pivot_table(index=["state", "state_abbr", "visa_type", "visa_group", "fy", "fy_end"],
                            columns="direction", values="persons", aggfunc="sum").reset_index()
    wide.columns.name = None
    wide["net"] = wide["arrivals"] - wide["departures"]

    sec = df[df["item"].isin(sectors)].copy()
    sec["sector"] = sec["item"].str.replace("Student - ", "", regex=False)
    sec = sec.pivot_table(index=["state", "sector", "fy"], columns="direction",
                          values="persons", aggfunc="sum").reset_index()
    sec.columns.name = None
    sec["net"] = sec["arrivals"] - sec["departures"]
    return wide, sec, df


def check_visa_totals(wide, raw):
    """Groups + derived unknown must reproduce the published totals exactly,
    and the states should add to Australia within rounding (ABS rounds to 10)."""
    pub = raw[raw["item"] == "Total"].pivot_table(index=["state", "fy"], columns="direction", values="persons")
    ours = wide.groupby(["state", "fy"])[["arrivals", "departures"]].sum()
    assert (pub - ours).abs().max().max() == 0

    states = wide[wide["state"] != "Australia"].groupby("fy")["net"].sum()
    aus = wide[wide["state"] == "Australia"].groupby("fy")["net"].sum()
    gap = (aus - states)
    log(f"visa cube check: Australia net minus sum of 8 states ranges {gap.min():,.0f} to {gap.max():,.0f} "
        "persons (Other Territories + rounding)")


# ---------------------------------------------------------------------------
# ABS time series spreadsheets (310102 components, 310104 ERP)
# ---------------------------------------------------------------------------

def read_abs_timeseries(path):
    """Standard ABS time-series layout: row 1 is the series description,
    rows 2-10 are metadata, data starts on row 11 in sheet Data1."""
    raw = pd.read_excel(path, sheet_name="Data1", header=None)
    names = raw.iloc[0, 1:].tolist()
    ids = raw.iloc[9, 1:].tolist()
    data = raw.iloc[10:].copy()
    data.columns = ["date"] + ids
    data["date"] = pd.to_datetime(data["date"])
    long = data.melt(id_vars="date", var_name="series_id", value_name="value")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    meta = pd.DataFrame({"series_id": ids, "description": names})
    long = long.merge(meta, on="series_id")
    before = len(long)
    long = long.dropna(subset=["value"])
    log(f"{path.name}: {len(ids)} series, {before:,} cells, dropped {before - len(long):,} empty cells")
    parts = long["description"].str.split(";").apply(lambda p: [x.strip() for x in p if x.strip()])
    long["measure"] = parts.str[0]
    long["state"] = parts.str[-1]
    return long


def tidy_population(components_path=COMPONENTS_FILE, erp_path=ERP_FILE):
    comp = read_abs_timeseries(components_path)
    comp = comp.pivot_table(index=["date", "state"], columns="measure", values="value").reset_index()
    comp.columns.name = None
    comp = comp.rename(columns={
        "Natural Increase": "natural_increase", "Net Overseas Migration": "nom",
        "Net Interstate Migration": "net_interstate",
        "Change Over Previous Quarter": "pop_change"})

    erp = read_abs_timeseries(erp_path)
    # 310104 has Male / Female / Persons in the description; I only want Persons.
    erp = erp[erp["description"].str.contains("Persons")]
    erp = erp[["date", "state", "value"]].rename(columns={"value": "erp"})

    q = comp.merge(erp, on=["date", "state"], how="left")
    q["state_abbr"] = q["state"].map(STATE_ABBR)
    # ABS dates the quarter by its first day of the last month (e.g. 2026-03-01 = March qtr).
    q["quarter_end"] = q["date"] + pd.offsets.MonthEnd(0)
    q = q.drop(columns="date").sort_values(["state", "quarter_end"])
    log(f"population: {len(q):,} state-quarter rows, {q['quarter_end'].min():%b %Y} to {q['quarter_end'].max():%b %Y}")
    return q


# ---------------------------------------------------------------------------
# Home Affairs BP0019, temporary visa holders in Australia
# ---------------------------------------------------------------------------

def read_bp0019_cache(path=BP0019_FILE):
    """The visible pivot table only shows snapshots from June 2018 on, because
    the earlier dates are hidden in the pivot filter. The full history (from
    Dec 2011) is still inside the pivot cache, so I read the cache XML directly
    instead of the worksheet."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as z:
        definition = ET.fromstring(z.read("xl/pivotCache/pivotCacheDefinition1.xml"))
        fields, lookups = [], []
        for cf in definition.iter(f"{ns}cacheField"):
            fields.append(cf.get("name"))
            shared = cf.find(f"{ns}sharedItems")
            lookups.append([item.get("v") for item in shared] if shared is not None else [])

        records = []
        with z.open("xl/pivotCache/pivotCacheRecords1.xml") as f:
            for _, el in ET.iterparse(f):
                if el.tag != f"{ns}r":
                    continue
                row = []
                for i, cell in enumerate(el):
                    v = cell.get("v")
                    if cell.tag == f"{ns}x":
                        row.append(lookups[i][int(v)])
                    elif cell.tag == f"{ns}m":
                        row.append(None)
                    else:
                        row.append(v)
                records.append(row)
                el.clear()

    df = pd.DataFrame(records, columns=fields)
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    n_before = len(df)
    df["visa_holders"] = pd.to_numeric(df["visa_holders"], errors="coerce")
    log(f"BP0019: read {n_before:,} pivot-cache records, {df['snapshot_date'].nunique()} snapshots "
        f"({df['snapshot_date'].min():%b %Y} to {df['snapshot_date'].max():%b %Y})")
    log(f"BP0019: {df['visa_holders'].isna().sum():,} records had a non-numeric count (e.g. '<5') and were set to missing")
    return df


def check_bp0019_against_sheet(cache, path=BP0019_FILE):
    """Re-total the cache and compare with the numbers shown on the sheet."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb["Visa Holders"].iter_rows(values_only=True))
    header = rows[9]
    shown = {}
    for r in rows[10:21]:
        for d, v in zip(header[1:], r[1:]):
            shown[(r[0], pd.Timestamp(d))] = v
    ours = cache.groupby(["visa_category", "snapshot_date"])["visa_holders"].sum()
    diffs = [abs(ours[k] - v) for k, v in shown.items()]
    log(f"BP0019 check: compared {len(diffs)} category-snapshot cells with the visible pivot, max difference {max(diffs):,.0f}")


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)

    raw_visa = read_visa_cube()
    visa, sectors, raw_long = tidy_visa_cube(raw_visa)
    check_visa_totals(visa, raw_long)
    visa.to_csv(PROCESSED / "nom_by_state_visa_fy.csv", index=False)
    sectors.to_csv(PROCESSED / "student_sectors_fy.csv", index=False)
    log(f"wrote nom_by_state_visa_fy.csv ({len(visa):,} rows) and student_sectors_fy.csv ({len(sectors):,} rows)")

    pop = tidy_population()
    pop.to_csv(PROCESSED / "population_components_quarterly.csv", index=False)
    log(f"wrote population_components_quarterly.csv ({len(pop):,} rows)")

    cache = read_bp0019_cache()
    check_bp0019_against_sheet(cache)
    by_cat = (cache.groupby(["snapshot_date", "visa_category", "applicant_type"], as_index=False)["visa_holders"].sum())
    by_cat.to_csv(PROCESSED / "temp_visa_holders_by_category.csv", index=False)
    log(f"wrote temp_visa_holders_by_category.csv ({len(by_cat):,} rows; citizenship and subclass summed out)")

    # Student and graduate holders by citizenship, for the "who is still here" question.
    sg = cache[cache["visa_category"].isin(["Student", "Temporary Graduate"])]
    by_cit = sg.groupby(["snapshot_date", "visa_category", "citizenship_country"], as_index=False)["visa_holders"].sum()
    by_cit.to_csv(PROCESSED / "student_graduate_holders_by_citizenship.csv", index=False)
    log(f"wrote student_graduate_holders_by_citizenship.csv ({len(by_cit):,} rows)")

    # A small sample of the record-level cache so the shape is visible on GitHub.
    cache.sample(2000, random_state=1).sort_values(["snapshot_date", "visa_category"]).to_csv(
        PROCESSED / "bp0019_cache_sample.csv", index=False)
    return log_lines


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
