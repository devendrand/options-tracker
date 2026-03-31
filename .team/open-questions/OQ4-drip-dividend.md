# OQ4: DRIP Dividend Handling

**Question:** Dividend reinvestment (DRIP) transactions in the CSV appear as a paired pattern: one `Dividend` row with a negative amount (debit — shares purchased) and a companion `Dividend` row with a positive amount (credit — cash dividend). Should these be linked and treated as a net-zero cash event, or tracked independently?

**Resolution:** **Track independently as two separate `DIVIDEND` `Transaction` records. Do not pair or net them. Do not create `EquityPosition` records from the DRIP debit row in v0.1.**

**Rationale:**
DRIP is not an internal transfer — both legs represent real economic events (dividend income received and shares acquired). Treating them as net-zero would incorrectly erase dividend income from the user's record.

Attempting to detect and pair DRIP rows in v0.1 introduces fragile pattern-matching logic: the two rows share the same activity type (`Dividend`) but differ in amount sign, and there is no guaranteed column linking them as a pair. The negative-amount row does not have a distinct activity type that identifies it as a DRIP purchase. Over-engineering this pairing logic in MVP carries high risk of false positives (e.g. treating two legitimate separate dividend payments on the same date as a DRIP pair).

The debit row (negative amount) technically represents shares purchased, which would ideally create an `EquityPosition`. However, without a reliable linking mechanism, and since DRIP fractional shares are typically small and not traded, deferring EquityPosition creation from DRIP to v1.0 is the pragmatic choice.

**Impact on implementation:**
- No special handling required — both DRIP rows classify as `DIVIDEND` via the standard `Activity Type = Dividend` mapping (Section 3.2.1)
- The classifier does NOT need DRIP-specific logic in v0.1
- No `EquityPosition` is created from `DIVIDEND` transactions in v0.1
- The Transactions Page will show both rows as `DIVIDEND` category with their respective amounts (one positive, one negative); users can identify the pair visually by date and amount
- Add to backlog for v1.0: DRIP detection and optional EquityPosition creation from DRIP debit rows
- **Open for v1.0:** DRIP pairing and equity lot creation from reinvestment purchases
