---
name: CSV Parser Conventions
description: E*TRADE CSV parsing rules established in F-06, including a csv.DictReader quirk that eliminates one guard branch
type: project
---

`csv.DictReader` silently skips completely blank lines — they never appear during iteration. The `_is_data_row` guard therefore does NOT need a `if not raw_date: return False` branch; only the date-regex check is needed to filter disclaimer footer rows. Adding the blank-string guard creates an unreachable branch that breaks 100% branch coverage.

**Why:** Discovered during F-06 TDD cycle when the blank-guard branch appeared as uncovered in pytest-cov output. Removing it simplified the code and restored 100% coverage.

**How to apply:** When writing row-filtering helpers for csv.DictReader output, do not add a separate empty-string guard — rely on the regex match returning falsy for both empty strings and non-date text.

Also: multi-column CSV header strings that exceed the 100-char ruff line limit must be split across lines using implicit string concatenation, not a backslash continuation.
