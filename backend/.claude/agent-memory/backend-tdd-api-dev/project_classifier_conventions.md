---
name: Transaction Classifier Conventions
description: Classification logic, disambiguation rules, and test patterns for F-07 classify_transaction
type: project
---

The classifier (`app/services/classifier.py`) is a pure function: `ParsedRow` in, `TransactionCategory` out.

Two lookup dicts drive all logic:
- `_UNAMBIGUOUS`: activity type string → category (no `is_option` check needed)
- `_AMBIGUOUS`: activity type → `(option_category, equity_category)` tuple; dispatches on `ParsedRow.is_option`

Fallback for unknown activity types: `TransactionCategory.OTHER`.

Activity types are `.strip()`ped before lookup — whitespace variants must work.

**OQ4 (DRIP):** Both DRIP legs (`Activity Type = Dividend`) map via the standard `Dividend → DIVIDEND` path. No special DRIP branch exists in the classifier.

**OQ5 (Bought To Open / Sold To Close):** These are in `_UNAMBIGUOUS` — no `is_option` check needed. Only `Sold Short` and `Bought To Cover` are in `_AMBIGUOUS`.

**Why:** Plan docs in `.team/features/F-07-transaction-classifier/plan/plan.md` record both resolutions.

**How to apply:** If adding new activity types, put unambiguous ones in `_UNAMBIGUOUS` and description-dependent ones in `_AMBIGUOUS`. Never add branching logic inside `classify_transaction` itself.
