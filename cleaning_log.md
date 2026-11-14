# Cleaning log

All of this happens in `src/prepare_data.py`. Raw files in `data/raw` are never edited.
Row counts below come from the script's own output, from the run on 15 Nov 2026.

## ABS Overseas Migration, data cube 4 (`34070DO004_202425.xlsx`)

| Step | Rows / cells |
|---|---|
| 9 tables (Australia + 8 states/territories) read into long form | 6,426 cells |
| Kept: the 11 main visa/citizenship rows | 4,158 |
| Set aside: subtotal and total rows (used only for checks) | 1,134 |
| Set aside: the three "Student - ..." sector rows | 1,134 |
| Added: derived "unknown visa" row (Total minus the 11 groups) | 378 |
| Output `nom_by_state_visa_fy.csv` (arrivals, departures, net per state x group x year) | 2,268 rows |
| Output `student_sectors_fy.csv` | 567 rows |

Problems I hit:

- The header row isn't in the same place on every sheet. Table 4.1 (Australia) has nine footnotes and the state tables have eight, so the header is on row 16 for Australia and row 15 for the states. I find it by looking for "Direction" in column A instead of hard-coding a row.
- Row labels carry footnote letters ("Total(i)", "2024-25(g)", "New Zealand citizens (subclass 444)(h)"), and the letters differ between sheets. I strip anything matching `(a)` to `(z)`.
- The "Direction" and visa group columns are only filled on the first row of each block, like merged cells. I forward-fill them.
- "Student" is already the sum of the three "Student - ..." sector rows underneath it. Keeping all four would double count students, so the sector rows go to their own file.
- There's no row for travellers with an unknown visa, but the published "Total" includes them. I back them out as Total minus the 11 groups. Some of these come out slightly negative (as low as -30), which is just the ABS rounding every cell to the nearest 10.
- The Contents sheet labels the file `34070DO004_202324` even though everything in it is 2024-25. It looks like a leftover from the previous release. I went by the table titles and the release date instead.
- Check: the 11 groups plus the derived unknown row reproduce every published Total exactly. Australia minus the sum of the 8 states is between -20 and +60 people a year (Other Territories plus rounding).

## ABS National, state and territory population, March 2026 (`310102.xlsx`, `310104.xlsx`)

| Step | Rows / cells |
|---|---|
| 310102: 35 series x 180 quarters | 6,300 cells, 9 empty dropped |
| 310104: 27 series x 180 quarters | 4,860 cells, 0 dropped |
| Kept "Persons" only from 310104 (dropped Male and Female) | 18 of 27 series dropped |
| Output `population_components_quarterly.csv` | 1,620 rows (9 geographies x 180 quarters) |

Problems I hit:

- Standard ABS time-series layout: the series name is on row 1, metadata on rows 2 to 10, data from row 11. The series name is a semicolon-separated string ("Net Overseas Migration ;  New South Wales ;"), which I split into measure and state.
- The 9 empty cells are the first quarter (June 1981) of "Change Over Previous Quarter", which has nothing to compare against.
- Australia has no net interstate migration series, which makes sense. Those cells are blank in the output.
- The ABS dates each quarter by the first day of its last month (2026-03-01 means the March quarter). I shifted to month-end so these line up with the Home Affairs snapshot dates.

## Home Affairs BP0019, temporary visa holders (`bp0019l-...-2026-09-30-v100.xlsx`)

| Step | Rows |
|---|---|
| Pivot cache records read | 308,631 |
| Records with a non-numeric count | 0 |
| Output `temp_visa_holders_by_category.csv` (date x category x applicant type) | 1,140 rows |
| Output `student_graduate_holders_by_citizenship.csv` | 20,422 rows |
| Output `bp0019_cache_sample.csv` (random 2,000 records, so the raw shape is visible) | 2,000 rows |

Problems I hit:

- The visible pivot table on the "Visa Holders" sheet starts at June 2018. The snapshots from December 2011 to March 2018 are there, just hidden by a filter on the pivot. Rather than unhide them in Excel (which would mean editing the raw file), I read the pivot cache XML inside the .xlsx directly. That gives every record with all its dimensions.
- Check: I re-totalled the cache by category and date and compared it with the 374 numbers visible on the sheet. Max difference 0.
- The explanatory notes say counts of 1 to 4 are shown as "<5". None of the cache records had a text value, so nothing was lost there.
- Note 6 says subclass 449 was dropped from July 2025, and note 7 says the figures come from a new data source and were revised. Both are definition changes in the middle of the series. They're small next to the changes I'm looking at, but they're listed in the README limitations.
- Snapshots are strongly seasonal (students away over summer, visitors up at Christmas). This isn't a cleaning step, but it's why the analysis only compares June with June.
