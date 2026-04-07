---
name: E*TRADE CSV Format — Real vs Test Fixture
description: Real E*TRADE CSV has 13 columns; parser normalises headers before DictReader; helpers accept str | None
type: project
---

The real E*TRADE CSV export has 13 columns and a different preamble than the simplified test fixtures.

## Real CSV format (SamoleTxnHistory.csv)
- **Preamble**: 6 lines (All Transactions Activity Types / blank / Account Activity... / blank / Total:,-921.88 / blank)
- **Header**: `Activity/Trade Date, Transaction Date, Settlement Date, Activity Type, Description, Symbol, Cusip, Quantity #, Price $, Amount $, Commission, Category, Note`
- **Key differences from test fixture**: `Quantity #` (not `Quantity`), `Activity/Trade Date` as a separate column, extra columns: `Cusip`, `Category`, `Note`
- **Empty fields**: blank quantity/price produce `""` from csv.DictReader (not `None`), e.g. dividend rows with `,,`
- **Options descriptions**: multi-space format, e.g. `CALL NVDA   06/18/26   220.000` (extra spaces between tokens); the `\s+` in the regex handles this

## Parser normalisation (etrade.py lines 233-235)
Header is normalised before passing to csv.DictReader:
- `Quantity #` → `Quantity`
- `Activity/Trade Date` → `Trade Date` (parser still reads `Transaction Date` for the date value)

## Helper function defensive design
All helpers (`_parse_optional_decimal`, `_parse_commission`, `_parse_optional_symbol`, `_parse_price`, `_parse_optional_date`) accept `str | None` and use `(value or "").strip()` internally, guarding against csv.DictReader restval `None` for rows with fewer columns than the header.

**Why:** `_is_data_row` filters out malformed rows before parsing, so `None` values don't reach helpers in practice. But the defensive coding avoids AttributeError on edge cases and satisfies mypy.

## Test fixtures
- `_make_csv()` / `_row()` — 9-column legacy format (test fixtures)
- `_make_real_csv()` / `_real_row()` — 13-column real format (added in TestRealETradeFormat)
- Both fixture sets are in `tests/unit/test_etrade_parser.py`

## Pre-existing ruff lint error
`app/schemas/position.py:10` has an unused `pydantic.Field` import (`F401`). This is pre-existing and unrelated to parser work.
