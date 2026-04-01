# F-06 Review — E*TRADE CSV Parser

**Reviewer:** tech-lead-architect
**Date:** 2026-03-31
**Verdict:** APPROVED

## Checklist

- [x] Preamble skip (rows 1-6) correct
- [x] Header row 7 handled correctly
- [x] Sentinel `--` to None for all fields
- [x] Date parsing MM/DD/YY to 20YY correct
- [x] Commission defaults to 0.00 when blank
- [x] Quantity stored as absolute value
- [x] Options regex matches CLAUDE.md pattern exactly
- [x] Option Expired price defaults to 0.00
- [x] Trailing blank/disclaimer rows skipped
- [x] ParsedRow dataclass has all required fields
- [x] OQ4 (DRIP) addressed — pass-through with no special handling, documented
- [x] OQ5 (Bought To Open / Sold To Close) addressed — all activity type variants tested
- [x] Tests are comprehensive and cover all edge cases

## Findings

### Quality Gates

All four CI gates pass clean:

- `ruff check`: all checks passed
- `ruff format --check`: 33 files already formatted
- `mypy app`: success, no issues found in 21 source files
- `pytest --cov=app --cov-branch --cov-fail-under=100`: 240 tests passed, 100% line and branch coverage — `etrade.py` is at 100% line and branch (104 statements, 22 branches, 0 missing)

### Implementation Correctness

**Preamble and header handling:** `_PREAMBLE_LINE_COUNT = 6` is correct. The implementation slices `lines[6:]` and feeds to `csv.DictReader`, meaning line index 6 (row 7) becomes the DictReader header. This is correct.

**Sentinel handling:** The `_SENTINEL = "--"` constant is applied consistently in `_parse_optional_decimal`, `_parse_optional_date`, `_parse_optional_symbol`, `_parse_commission`, and `_parse_price`. All nullable fields return `None` for `--`; commission returns `Decimal('0.00')`. Correct per domain rules.

**Date parsing:** `_parse_date` applies `2000 + int(year_2)` — this always yields 20YY which matches the domain rule exactly. The edge cases year 00 (→ 2000) and year 99 (→ 2099) are both tested.

**Options regex:** The compiled pattern `^(CALL|PUT)\s+(\S+)\s+(\d{2}/\d{2}/\d{2})\s+([\d.]+)` with `re.IGNORECASE` matches the pattern specified in CLAUDE.md verbatim. `re.IGNORECASE` is a reasonable defensive addition since E*TRADE uses uppercase in practice.

**Option Expired price:** `_parse_price` correctly checks `activity_type.strip() == "Option Expired"` when the price field is blank or `--`, returning `Decimal('0.00')` only for that activity type while returning `None` for all other activity types with blank prices. Both the blank-field and sentinel variants are tested.

**Quantity as absolute value:** `abs(raw_quantity)` applied after the optional decimal parse. Negative quantities in CSV become positive. Fractional quantities (D21) are preserved. Correct.

**Trailing row filtering:** `_is_data_row` uses `re.match(r"^\d{2}/\d{2}/\d{2}$", raw_date)` on the `Transaction Date` column. This elegantly handles both completely blank rows (DictReader skips empty lines) and disclaimer footer rows that have non-date text in the first column. This is a robust approach.

**`raw_data` fidelity:** The raw CSV row dict is captured as `dict(row)` before any field transformation, preserving the original sentinel values (e.g., `--` is stored in `raw_data` even when the parsed field is `None`). This is correct and required for the `RawTransaction.raw_data` JSONB audit trail.

### OQ4 — DRIP Dividend Handling

Correctly resolved as pass-through: no DRIP-specific logic in the parser. Both positive-amount credit and negative-amount debit rows parse as standard `Dividend` rows. Three tests verify the resolution: individual credit row, individual debit row, and both rows in a pair. Clean.

### OQ5 — Activity Type Variants

All required activity type variants are tested:
- Unambiguous options variants: `Bought To Open`, `Sold To Close`, `Bought To Close`, `Sold To Open`
- Ambiguous variants requiring description regex disambiguation: `Sold Short` (3 equity + 1 options description), `Bought To Cover` (3 equity + 1 options description)
- Options lifecycle: `Option Assigned`, `Option Exercised`, `Option Expired`

The plan required "at minimum 3 concrete description examples per variant for `Sold Short`/`Bought To Cover`". The implementation meets this with 3 equity-description tests and 1 options-description test per variant.

### ParsedRow Dataclass

All 15 fields are present and correctly typed. `commission` is typed as `Decimal` (never `None`), which is the correct non-optional contract. The `raw_data: dict[str, str]` field correctly models the verbatim CSV row for JSONB storage.

### Test Quality

The test suite is thorough and well-organized. Test classes map directly to logical categories: basic parsing, preamble/trailer handling, sentinel handling, date parsing, commission defaults, quantity absolute value, options regex extraction, non-option activity types, Option Expired, DRIP (OQ4), activity type variants (OQ5), ParsedRow model integrity, and edge cases. The `_make_csv` and `_row` helper functions keep fixtures DRY and readable.

One commendable detail: `test_raw_data_preserves_original_sentinel_value` explicitly verifies that `raw_data["Symbol"] == "--"` while `row.symbol is None`, which is the most important invariant for audit trail correctness.

### Minor Observations (no action required)

- The module docstring references `ParsedTransaction` in the OQ4/OQ5 note from the plan but the actual class is named `ParsedRow`. The plan was written before the implementation; the implementation name `ParsedRow` is cleaner and used consistently throughout. No issue.
- `re.IGNORECASE` on the options regex provides extra tolerance for lowercase input, which is a safe defensive choice that has no correctness impact.

## Verdict

APPROVED. The E*TRADE CSV parser is a clean, pure-function implementation with no I/O side effects. All CLAUDE.md domain rules are implemented correctly. Both open questions (OQ4, OQ5) are resolved and tested per their documented resolutions. Coverage is 100% line and branch. No issues to address before merging.
