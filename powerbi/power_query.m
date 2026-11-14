// Power Query (M) for the overseas migration report.
// Create a text parameter called DataFolder pointing at data/processed, e.g.
//   C:\Users\<you>\overseas_migration_after_2020\data\processed\
// then make one blank query per section below (Home > New Source > Blank Query > Advanced Editor).

// ---------------------------------------------------------------------------
// FactNOM  (from nom_by_state_visa_fy.csv)
// Australia rows are removed: the report adds up the eight states instead, so
// slicers work the same way on every visual. National totals will be 20-60
// people a year off the published figure (Other Territories + rounding).
// ---------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(DataFolder & "nom_by_state_visa_fy.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"state", type text}, {"state_abbr", type text}, {"visa_type", type text},
        {"visa_group", type text}, {"fy", type text}, {"fy_end", Int64.Type},
        {"arrivals", Int64.Type}, {"departures", Int64.Type}, {"net", Int64.Type}}),
    StatesOnly = Table.SelectRows(Typed, each [state] <> "Australia"),
    // Join key to DimDate: 30 June of the year the financial year ends.
    AddFYEndDate = Table.AddColumn(StatesOnly, "fy_end_date", each #date([fy_end], 6, 30), type date),
    Removed = Table.RemoveColumns(AddFYEndDate, {"state", "visa_type"})
in
    Removed

// ---------------------------------------------------------------------------
// FactPopulation  (from population_components_quarterly.csv)
// ---------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(DataFolder & "population_components_quarterly.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"state", type text}, {"state_abbr", type text}, {"quarter_end", type date},
        {"natural_increase", Int64.Type}, {"nom", Int64.Type}, {"net_interstate", Int64.Type},
        {"pop_change", Int64.Type}, {"erp", Int64.Type}}),
    StatesOnly = Table.SelectRows(Typed, each [state] <> "Australia"),
    From2010 = Table.SelectRows(StatesOnly, each [quarter_end] >= #date(2010, 1, 1)),
    Removed = Table.RemoveColumns(From2010, {"state"})
in
    Removed

// ---------------------------------------------------------------------------
// FactVisaHolders  (from temp_visa_holders_by_category.csv)
// National only: BP0019 has no state breakdown.
// ---------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(DataFolder & "temp_visa_holders_by_category.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"snapshot_date", type date}, {"visa_category", type text},
        {"applicant_type", type text}, {"visa_holders", Int64.Type}}),
    // Snapshots are seasonal, so flag June ones for like-for-like comparisons.
    AddIsJune = Table.AddColumn(Typed, "is_june_snapshot", each Date.Month([snapshot_date]) = 6, type logical)
in
    AddIsJune

// ---------------------------------------------------------------------------
// DimState  (typed by hand; 8 rows)
// ---------------------------------------------------------------------------
let
    Source = #table(
        type table [state_abbr = text, state_name = text, sort_order = Int64.Type],
        {{"NSW", "New South Wales", 1}, {"Vic", "Victoria", 2}, {"Qld", "Queensland", 3},
         {"SA", "South Australia", 4}, {"WA", "Western Australia", 5}, {"Tas", "Tasmania", 6},
         {"NT", "Northern Territory", 7}, {"ACT", "Australian Capital Territory", 8}})
in
    Source

// ---------------------------------------------------------------------------
// DimVisaGroup  (distinct groups from FactNOM, plus a broad type and a sort order)
// ---------------------------------------------------------------------------
let
    Source = Csv.Document(File.Contents(DataFolder & "nom_by_state_visa_fy.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Groups = Table.Distinct(Table.SelectColumns(Promoted, {"visa_type", "visa_group"})),
    AddChartType = Table.AddColumn(Groups, "chart_type", each
        if [visa_type] = "Temporary" then "Temporary visas"
        else if [visa_type] = "Permanent" then "Permanent visas"
        else "Citizens and unknown", type text),
    AddSort = Table.AddColumn(AddChartType, "sort_order", each
        if [visa_type] = "Temporary" then 1 else if [visa_type] = "Permanent" then 2 else 3, Int64.Type)
in
    AddSort

// ---------------------------------------------------------------------------
// DimDate  (daily calendar, Australian financial year)
// ---------------------------------------------------------------------------
let
    StartDate = #date(2004, 7, 1),
    EndDate = #date(2026, 12, 31),
    Dates = List.Dates(StartDate, Duration.Days(EndDate - StartDate) + 1, #duration(1, 0, 0, 0)),
    ToTable = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),
    Typed = Table.TransformColumnTypes(ToTable, {{"Date", type date}}),
    AddFYEnd = Table.AddColumn(Typed, "FY end year", each
        if Date.Month([Date]) >= 7 then Date.Year([Date]) + 1 else Date.Year([Date]), Int64.Type),
    AddFY = Table.AddColumn(AddFYEnd, "Financial year", each
        Text.From([FY end year] - 1) & "-" & Text.End(Text.From([FY end year]), 2), type text),
    AddQuarterEnd = Table.AddColumn(AddFY, "Quarter end", each Date.EndOfQuarter([Date]), type date),
    AddIsBaseline = Table.AddColumn(AddQuarterEnd, "Is baseline FY", each
        [FY end year] >= 2016 and [FY end year] <= 2019, type logical)
in
    AddIsBaseline

// ---------------------------------------------------------------------------
// ExcessStep  (disconnected table that drives the waterfall on page 2)
// ---------------------------------------------------------------------------
let
    Source = #table(
        type table [step = text, step_order = Int64.Type],
        {{"Arrivals vs normal", 1}, {"Fewer departures than normal", 2}})
in
    Source
