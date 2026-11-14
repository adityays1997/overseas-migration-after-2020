# Power BI build notes

The .pbix isn't in the repo (it's binary and changes every time you open it). This folder has
everything needed to rebuild it from `data/processed`:

- `power_query.m` has one query per table
- `measures.dax` has the 10 measures, each with a comment on what it does and why

## Data model

A star schema with three fact tables at different grains. They share the date and state
dimensions, but they are never summed together.

```
                  DimState (8 rows)
                 /                 \
   FactNOM ------                   ------ FactPopulation
   state x visa group x FY                  state x quarter
   arrivals, departures, net                nom, erp, natural increase, interstate
        |   \                                   |
        |    DimVisaGroup (12 rows)             |
        |                                       |
        +-------------- DimDate ----------------+
                           |
                    FactVisaHolders
                    snapshot x visa category x applicant type
                    (national only, no state key)

   ExcessStep (2 rows, disconnected, feeds the waterfall)
```

| Table | Grain | Key columns | Notes |
|---|---|---|---|
| FactNOM | state, visa group, financial year | state_abbr, visa_group, fy_end_date | Joined to DimDate on 30 June of the FY end year. Australia rows removed. |
| FactPopulation | state, quarter | state_abbr, quarter_end | Filtered to 2010 onward to keep the model small. |
| FactVisaHolders | snapshot, category, applicant type | snapshot_date | Stock, not flow. Never sum across dates (see measure 9). |
| DimDate | day | Date | Australian financial year columns plus an `Is baseline FY` flag for 2015-16 to 2018-19. |
| DimState | state | state_abbr | Sort order column so states don't come out alphabetical. |
| DimVisaGroup | visa group | visa_group | `chart_type` rolls the 12 groups into 3 for the stacked chart. |
| ExcessStep | waterfall step | step | Disconnected. |

Mark DimDate as a date table. Set `DimState[state_name]` to sort by `sort_order`, and do the
same for `DimVisaGroup[chart_type]`.

FactVisaHolders has no state column, so the State slicer won't filter it. On page 4, turn off
the slicer's interaction with those visuals (Format > Edit interactions). That way nobody
reads a national number as a state one.

## Power Query steps in plain words

1. Create a `DataFolder` text parameter pointing at `data/processed\`.
2. FactNOM: load CSV, set types, remove the Australia rows, add `fy_end_date` = 30 June of `fy_end`, drop the long state name.
3. FactPopulation: load CSV, set types, remove Australia, keep quarters from 2010.
4. FactVisaHolders: load CSV, set types, add an `is_june_snapshot` flag.
5. DimState and ExcessStep: typed straight into M with `#table`.
6. DimVisaGroup: distinct visa groups from the NOM CSV, plus a 3-way `chart_type` and a sort order.
7. DimDate: daily calendar July 2004 to Dec 2026 with FY end year, FY label, quarter end, and baseline flag.

## Report pages

**Page 1: Overview**
- Top row of cards: NOM per 1,000 Residents (latest quarter), Pre-COVID NOM per 1,000, Temp Visa Holders, Temp Visa Holders Change vs Jun 2019.
- Main visual: stacked column of NOM Net by `Financial year`, legend `DimVisaGroup[chart_type]`. Add NOM Net as a line on the same chart (line and stacked column visual, same axis).
- Below it: line chart of NOM Arrivals and NOM Departures by financial year. Filter it to visa_type = Temporary.
- Slicers (one row at the top): State (dropdown, multi-select), Visa type.

**Page 2: Arrivals or departures?**
- Waterfall: Category = `ExcessStep[step]`, Values = Excess Step Value. Page-level filter on FY end year 2021 to 2025.
- Bar chart: Excess Net vs Baseline by visa_group, sorted descending. Same page filter.
- Matrix: rows = visa_group, values = NOM Arrivals, NOM Departures, NOM Net, Excess Net vs Baseline. Conditional formatting (data bars) on the excess column.
- Slicer: State.

**Page 3: States**
- Line chart with small multiples by `DimState[state_abbr]`. X = `DimDate[Quarter end]`, values = NOM per 1,000 Residents and Pre-COVID NOM per 1,000 (format the second as a dashed grey line). Filter quarters from June 2012.
- Table: state, Pre-COVID NOM per 1,000, latest NOM per 1,000, and a ratio column. Use a visual-level filter on the latest quarter.
- Slicer: date range on Quarter end.

**Page 4: Who is still here**
- Line chart: Temp Visa Holders by snapshot date, legend = visa_category, filtered to `is_june_snapshot` = TRUE.
- Clustered bar: Temp Visa Holders Change vs Jun 2019 by visa_category (latest June snapshot).
- Small note text box: "Home Affairs counts are national only and include Special Category (NZ) holders."
- Slicers: Visa category, Applicant type (primary or secondary). State slicer interactions off.

## Screenshots to take for the main README

1. Page 1 with no slicers applied, so the full national picture shows.
2. Page 2 waterfall on its own, cropped tight, with the page filter set to 2020-21 to 2024-25.
3. Page 3 small multiples, full width.
4. Page 3 with the State slicer set to WA, to show the rate line next to the pre-COVID line.
5. Page 4 line chart, June snapshots only.
6. The model view (Modelling > Model view), laid out so the star shape is visible. Reviewers look for this one.
7. One measure open in the formula bar, Excess Step Value is a good one, to show the DAX.

Save them as `images/powerbi_01_overview.png` and so on. The main README already has slots
for them under "Power BI version".
