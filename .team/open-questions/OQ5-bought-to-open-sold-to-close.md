# OQ5: `Bought To Open` / `Sold To Close` Activity Type Support

**Question:** `Bought To Open` and `Sold To Close` activity types are present in the CSV (in addition to `Sold Short` / `Bought To Cover`) and map unambiguously to `OPTIONS_BUY_TO_OPEN` and `OPTIONS_SELL_TO_CLOSE` respectively. Confirm that both activity type variants should be supported.

**Resolution:** **Confirmed. Both activity type variants MUST be supported.** This is not optional — it is a correctness requirement.

**Rationale:**
E*TRADE uses different activity type labels depending on the order entry path:
- Orders placed through the options-specific order entry flow use `Bought To Open` / `Sold To Close`
- Orders placed through the standard equity order flow (common for options-knowledgeable users who use the stock quote page) use `Sold Short` / `Bought To Cover`

Both paths result in the same economic transaction (opening/closing an options position). A parser that handles only one variant will silently misclassify or drop real options transactions from users who use both order entry flows. Given that both variants are already in the mapping table (Section 3.2.1 of the PRD), this is a straightforward implementation: no disambiguation logic needed for these two types (unlike `Sold Short` / `Bought To Cover` which require description-field regex).

**Impact on implementation:**
- `Bought To Open` → `OPTIONS_BUY_TO_OPEN` (unambiguous; no description check needed)
- `Sold To Close` → `OPTIONS_SELL_TO_CLOSE` (unambiguous; no description check needed)
- The classifier mapping table must include both variants
- Unit tests must include CSV rows with both `Bought To Open` and `Sold Short` for `BUY_TO_OPEN`, and both `Sold To Close` and `Bought To Cover` for `SELL_TO_CLOSE`, to confirm correct classification via both paths
- This is already reflected in the PRD mapping table — no schema changes needed; implementation must not omit these activity types
