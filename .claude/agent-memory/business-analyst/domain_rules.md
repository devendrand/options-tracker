---
name: Domain Rules
description: Options trading domain rules, terminology, and business logic patterns relevant to this application
type: reference
---

## Options Domain Terminology

- **Contract multiplier:** Standard US equity options = 100 shares per contract
- **Premium:** Price paid or received for an options contract (per share, multiply by 100 for contract value)
- **Covered call:** Short call + long 100 shares of same underlying
- **Cash-secured put:** Short put + sufficient cash to purchase shares at strike
- **Assignment:** Short option holder is obligated to buy (put) or sell (call) shares at strike
- **Exercise:** Long option holder chooses to buy (call) or sell (put) shares at strike
- **Expiry:** Contract reaches expiration date
- **Worthless expiry:** OTM option expires with no value; full premium collected (short) or lost (long)
- **Rolling:** Closing one options position and opening a new one (same or different strike/expiry) — often same-day
- **Spread:** Two or more options legs forming a defined-risk position (e.g., bull put spread, iron condor)

## P&L Sign Convention (standard)
- SELL_TO_OPEN: proceeds are POSITIVE (credit received)
- BUY_TO_OPEN: cost is NEGATIVE (debit paid)
- BUY_TO_CLOSE: cost is NEGATIVE (debit paid to close)
- SELL_TO_CLOSE: proceeds are POSITIVE (credit received to close)
- P&L = (total credits received) - (total debits paid) - commissions

## Assignment P&L Rules
- OPTIONS_ASSIGNED on short call: options position closes at intrinsic value; shares are called away at strike
- OPTIONS_ASSIGNED on short put: options position closes at intrinsic value; shares are put to buyer at strike
- The options leg P&L = premium received at open - assignment loss/gain
- Equity position created at cost basis = strike price (adjusted for premium if tracking combined P&L)

## Worthless Expiry P&L
- Short position: full premium collected = realized gain; close price = $0
- Long position: full premium paid = realized loss; close price = $0

## E*TRADE CSV Format Facts (confirmed from sample file SamoleTxnHistory.csv)

- 6 preamble rows before the header row (row 7 is the header)
- Trailing rows after data: blank rows + legal disclaimer text — must be skipped
- 13 columns: `Activity/Trade Date, Transaction Date, Settlement Date, Activity Type, Description, Symbol, Cusip, Quantity #, Price $, Amount $, Commission, Category, Note`
- Sentinel `--` = null/N/A for any field
- Settlement Date can be blank (empty string) for cash transactions
- Price field is blank (not `0`) on Option Expired rows
- Quantity is signed in CSV (negative = sell/short); must be stored as absolute value on Transaction
- Amount is cash-flow signed: positive = credit, negative = debit
- No broker transaction ID field — dedup uses composite key only
- Internal transfers (Activity Type = Transfer, description starts with TRNSFR) always come in +/- pairs on same date
- Fractional share quantities are present (equity DRIP buys) — Quantity must be Decimal, not integer, for equity

## All Distinct E*TRADE Activity Types (confirmed from sample)

- Online Transfer → TRANSFER (external bank transfer)
- Dividend → DIVIDEND
- Qualified Dividend → DIVIDEND
- Transfer → TRANSFER (internal TRNSFR pairs) or OTHER (unexpected)
- Bought → EQUITY_BUY
- Sold → EQUITY_SELL
- Sold Short → OPTIONS_SELL_TO_OPEN (if description matches options pattern) else EQUITY_SELL
- Bought To Cover → OPTIONS_BUY_TO_CLOSE (if description matches options pattern) else EQUITY_BUY
- Bought To Open → OPTIONS_BUY_TO_OPEN
- Sold To Close → OPTIONS_SELL_TO_CLOSE
- Option Expired → OPTIONS_EXPIRED
- Option Assigned → OPTIONS_ASSIGNED
- Interest Income → INTEREST
- Margin Interest → INTEREST

## E*TRADE Options Description Format
`(CALL|PUT)\s+<SYMBOL>\s+<MM/DD/YY>\s+<STRIKE>` (variable whitespace between fields)
Example: `CALL NVDA   06/18/26   220.000`
Symbol in Description = underlying (not OCC option symbol). Strike has 3 decimal places in CSV but is monetary (2dp internally).
