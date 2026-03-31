# Options Tracker — Product Requirements Document

**Version:** 0.4 (Broker corrected: E*TRADE, not Schwab)
**Date:** 2026-03-30
**Status:** In Review

---

## 1. Overview

Options Tracker is a web application that allows individual investors to upload brokerage transaction exports, automatically identify and classify options trades, match opening and closing legs of each position, and compute realized P&L. Non-options activity (equity purchases, dividends, transfers, fees) is retained for record-keeping but excluded from options analytics.

---

## 2. Goals

- Provide a single place to track the full lifecycle of options positions across multiple uploads and brokers.
- Detect and prevent duplicate transactions across uploads without losing data.
- Automatically classify options transaction types and compute realized P&L on closed positions, using correct sign conventions.
- Maintain a full audit trail from any transaction back to its source upload.
- Be deployable locally via Docker Compose with a single command.

---

## 3. Functional Requirements

### 3.1 Transaction Upload

- Users upload a CSV file. In MVP1, the broker is implicitly **E*TRADE** — the `broker` parameter is **not required** in the upload API (see D17). Auto-detection is not supported in v0.1.
- The system stores the raw upload record (filename, broker, timestamp, uploader metadata).
- Every parsed transaction is linked to the upload it came from.

#### 3.1.1 File-Level Validation

Before any parsing occurs, the system validates:
- File is valid UTF-8 or UTF-16 CSV.
- File does not exceed **10MB** or **10,000 rows**.
- File contains all required column headers for the declared broker format (E*TRADE: see column spec below).
- Filename matches the expected pattern `*TxnHistory*.csv` (advisory warning only — not a hard rejection).

If validation fails, the upload is **rejected** with a user-readable error listing specific failures. No records are written to the database.

#### 3.1.2 E*TRADE CSV Format Specification

The MVP1 broker format is the **E*TRADE account activity CSV export** (filename pattern: `*TxnHistory*.csv`).

**File structure:**

| Row(s) | Content |
|---|---|
| 1 | Report title (e.g. "All Transactions Activity Types") |
| 2 | Blank |
| 3 | Account description line (e.g. "Account Activity for Stocks -0067 from Current Year") |
| 4 | Blank |
| 5 | Totals line (e.g. `Total:,-921.88`) |
| 6 | Blank |
| 7 | **Column header row** |
| 8–N | Transaction data rows |
| N+1 onward | Trailing blank rows and legal disclaimer text |

Rows 1–6 are preamble and **must be skipped** during parsing. The parser must also skip any trailing blank or non-CSV rows at the end of the file (rows after the last valid transaction data row).

**Exact column headers (row 7):**

```
Activity/Trade Date, Transaction Date, Settlement Date, Activity Type, Description, Symbol, Cusip, Quantity #, Price $, Amount $, Commission, Category, Note
```

**Column semantics:**

| Column | Internal Field | Notes |
|---|---|---|
| `Activity/Trade Date` | `trade_date` | MM/DD/YY format |
| `Transaction Date` | `transaction_date` | MM/DD/YY format; same as trade date for most rows |
| `Settlement Date` | `settlement_date` | MM/DD/YY format; may be blank (``) for cash transactions |
| `Activity Type` | `activity_type` | See taxonomy in Section 3.2 |
| `Description` | `description` | Free text; options use structured format (see Section 3.2.1) |
| `Symbol` | `symbol` | Ticker symbol; `--` when not applicable |
| `Cusip` | `cusip` | CUSIP identifier; `--` when not applicable |
| `Quantity #` | `quantity` | Signed decimal; negative = sell/short, positive = buy/long; may be blank |
| `Price $` | `price` | Per-share or per-contract price; may be blank (e.g. on `Option Expired` rows) |
| `Amount $` | `amount` | Net cash impact; positive = credit to account, negative = debit; may be blank |
| `Commission` | `commission` | Total broker commission including all fees; `0.0` when no commission |
| `Category` | `category_raw` | Broker category label; `--` when not populated — do not use for classification |
| `Note` | `note` | Free text note; `--` when absent |

**Sentinel value:** `--` means null / not applicable. The parser must treat `--` as `None` for all fields.

**Signed quantity convention:**
- Negative quantity → sell or short (e.g. `Sold Short`, `Sold`)
- Positive quantity → buy or long (e.g. `Bought`, `Bought To Open`, `Bought To Cover`)
- `Option Expired` quantity sign reflects the original position direction (positive = was long, negative = was short)
- `Option Assigned` quantity is positive

**Signed amount convention (cash-flow):**
- Positive amount → cash credited to the account (premium received, proceeds from sale, dividend paid)
- Negative amount → cash debited from the account (premium paid, cost of purchase)

#### 3.1.3 Deduplication

There is **no broker transaction ID field** in the E*TRADE CSV format. Tier 1 deduplication does not apply to this format.

The only deduplication key for E*TRADE is the **Tier 2 composite key**:

```
(trade_date, transaction_date, settlement_date, activity_type, description, symbol, quantity, price, amount, commission)
```

- **Exact match on composite key (high-confidence duplicate):** The later upload's copy is marked `DUPLICATE`. First upload wins.
- **Collision on composite key (lower-confidence match):** Marked `POSSIBLE_DUPLICATE` and surfaced on the Upload History page for user review. Not auto-suppressed.

`RawTransaction.status` values: `ACTIVE | DUPLICATE | POSSIBLE_DUPLICATE | PARSE_ERROR`

#### 3.1.4 Internal Transfer Filtering

**Business rule — Paired internal transfers:**

When `Activity Type = Transfer` and the description starts with `TRNSFR` (e.g. `TRNSFR MARGIN TO CASH`, `TRNSFR CASH TO MARGIN`), the row represents an internal bookkeeping movement between the account's margin and cash sub-ledgers. These rows **always appear in pairs** on the same date with equal-and-opposite amounts (one credit, one debit) that net to zero.

A variant exists where the `Symbol` field is populated with a non-`--` ticker (e.g. `JPST`) and the description contains the security name followed by `TRNSFR CASH TO MARGIN` — this represents a fractional-share internal transfer. These also appear in paired +/− rows.

Processing rules:
- Both rows of a pair are stored as `RawTransaction` records with `category = TRANSFER`.
- Paired internal transfers (where the two legs net to zero on the same date) are **excluded from all analytics** — they do not create `Transaction` records.
- The parser should detect and flag the paired nature (matching amount magnitude, same date, same description prefix) and mark both legs with `is_internal_transfer = true` on the `RawTransaction` record.
- If a `TRNSFR` row cannot be paired (orphaned leg), it is stored with `status = PARSE_ERROR` and flagged for user review.

**Important:** `Online Transfer` rows (description contains `TRANSFER FROM` or `TRANSFER TO` with an external account reference ID) are **not** internal transfers. These are real external cash movements and must be retained as `TRANSFER` category `Transaction` records.

#### 3.1.5 Row-Level Parse Error Handling

Rows that fail individual field parsing (invalid date, non-numeric price, unrecognised action) are stored as `RawTransaction` records with `status = PARSE_ERROR`. The upload itself succeeds; the post-upload summary reports how many rows had parse errors. Parse-error rows do not produce `Transaction` records.

#### 3.1.6 Broker Support

- **MVP1 (v0.1):** E*TRADE CSV format only (this document). Broker parameter not required in upload API.
- **v0.2:** Additional broker formats (e.g. Tastytrade). Broker adapter pattern — each broker has a concrete adapter that normalises its CSV into the internal `ParsedTransaction` schema.

#### 3.1.7 Upload Soft-Delete

- A user can soft-delete an upload.
- Cascading behaviour: all `RawTransaction` and `Transaction` records from that upload are soft-deleted.
- If an `OptionsPosition` had its **only** open or close leg from the deleted upload, that position is also soft-deleted.
- If a position had its open leg from upload A and close leg from upload B, and upload B is deleted, the position **reverts to OPEN** status (close leg removed, not deleted).
- The system displays a warning when soft-deleting an upload: *"Deleting this upload may surface previously hidden duplicate transactions. Review the Transactions page after deletion."*

---

### 3.2 Transaction Classification

Each transaction is classified into one of the following internal categories. The classification is derived from the CSV `Activity Type` field and, for options-ambiguous types, the `Description` field.

| Internal Category | Description |
|---|---|
| `OPTIONS_SELL_TO_OPEN` | Opening a short options position (e.g. covered call, cash-secured put) |
| `OPTIONS_BUY_TO_OPEN` | Opening a long options position |
| `OPTIONS_BUY_TO_CLOSE` | Closing a short options position |
| `OPTIONS_SELL_TO_CLOSE` | Closing a long options position |
| `OPTIONS_EXPIRED` | Option reached expiry worthless (no exercise) |
| `OPTIONS_ASSIGNED` | Short option assigned; broker delivers/receives shares involuntarily |
| `OPTIONS_EXERCISED` | Long option exercised (voluntarily or at auto-exercise at expiry); shares delivered |
| `EQUITY_BUY` | Purchase of shares |
| `EQUITY_SELL` | Sale of shares |
| `DIVIDEND` | Dividend payment received (ordinary or qualified) |
| `TRANSFER` | Cash or asset transfer (external or internal) |
| `INTEREST` | Credit or debit interest on margin/cash balances |
| `FEE` | Account fees (maintenance, data, wire, etc.) |
| `JOURNAL` | Internal journal entries or sub-account transfers |
| `OTHER` | Anything that does not match the above |

Only `OPTIONS_*` categories participate in options P&L calculations.

**Quantity convention:** `quantity` on the internal `Transaction` record is always a **positive integer**. Direction is encoded in the `category` field (e.g. `BUY_TO_OPEN` vs `SELL_TO_OPEN`). The signed quantity from the CSV is used only during parsing to determine direction and must be stored as its absolute value.

#### 3.2.1 E*TRADE Activity Type → Internal Category Mapping

The following table maps every distinct `Activity Type` value observed in the E*TRADE CSV to the internal category. For `Sold Short` and `Bought To Cover`, the Description field must be inspected to determine whether the transaction is an options trade or an equity short sale (see Section 3.2.2).

| E*TRADE `Activity Type` | Condition | Internal Category | Notes |
|---|---|---|---|
| `Online Transfer` | — | `TRANSFER` | External cash in/out via online bank transfer; description contains external account reference ID (e.g. `REFID:...`) |
| `Dividend` | — | `DIVIDEND` | Ordinary dividend; may include dividend reinvestment (DRIP) rows |
| `Qualified Dividend` | — | `DIVIDEND` | Qualified dividend; treated identically to `Dividend` for classification purposes |
| `Transfer` | Description starts with `TRNSFR` | `TRANSFER` | Internal margin/cash bookkeeping transfer; always paired — see Section 3.1.4 |
| `Transfer` | Description does not start with `TRNSFR` | `OTHER` | Unexpected Transfer variant; flag for review |
| `Bought` | — | `EQUITY_BUY` | Purchase of equity shares or fractional shares |
| `Sold` | — | `EQUITY_SELL` | Sale of equity shares or fractional shares |
| `Sold Short` | Description matches options pattern | `OPTIONS_SELL_TO_OPEN` | Opening short options position (covered call, cash-secured put, naked short) |
| `Sold Short` | Description does not match options pattern | `EQUITY_SELL` | Equity short sale; treat as `EQUITY_SELL` |
| `Bought To Cover` | Description matches options pattern | `OPTIONS_BUY_TO_CLOSE` | Closing a short options position by buying back |
| `Bought To Cover` | Description does not match options pattern | `EQUITY_BUY` | Covering an equity short position; treat as `EQUITY_BUY` |
| `Bought To Open` | Description matches options pattern | `OPTIONS_BUY_TO_OPEN` | Opening a long options position |
| `Sold To Close` | Description matches options pattern | `OPTIONS_SELL_TO_CLOSE` | Closing a long options position by selling |
| `Option Expired` | — | `OPTIONS_EXPIRED` | Option reached expiry worthless; price and commission are always $0.00 |
| `Option Assigned` | — | `OPTIONS_ASSIGNED` | Short option assigned at expiry; triggers equity position creation |
| `Interest Income` | — | `INTEREST` | Credit interest (e.g. bank sweep interest) |
| `Margin Interest` | — | `INTEREST` | Debit interest charged on margin balance |

**Note on `Sold Short` / `Bought To Cover` disambiguation:** In this CSV format, E*TRADE uses `Sold Short` for both equity short selling and opening short options positions. The Description field is the authoritative discriminator. If the description matches the options pattern defined in Section 3.2.2, classify as options; otherwise classify as equity. The same logic applies to `Bought To Cover`.

#### 3.2.2 Options Description Parsing

Options transactions in the E*TRADE CSV use the following structured Description format:

```
<OPTION_TYPE>  <UNDERLYING_SYMBOL>  <EXPIRY_MM/DD/YY>  <STRIKE_PRICE>
```

**Field definitions:**

| Field | Format | Example |
|---|---|---|
| `OPTION_TYPE` | `CALL` or `PUT` | `CALL` |
| `UNDERLYING_SYMBOL` | Ticker of the underlying security | `NVDA` |
| `EXPIRY_MM/DD/YY` | Expiry date as `MM/DD/YY` (2-digit year) | `06/18/26` |
| `STRIKE_PRICE` | Strike price as a decimal number | `220.000` |

**Concrete examples:**

| Raw Description | Parsed Values |
|---|---|
| `CALL NVDA   06/18/26   220.000` | type=CALL, underlying=NVDA, expiry=2026-06-18, strike=220.00 |
| `PUT  SPY    04/24/26   600.000` | type=PUT, underlying=SPY, expiry=2026-04-24, strike=600.00 |
| `PUT  SPXW   02/20/26  6805.000` | type=PUT, underlying=SPXW, expiry=2026-02-20, strike=6805.00 |
| `CALL SLV    04/24/26    75.000` | type=CALL, underlying=SLV, expiry=2026-04-24, strike=75.00 |

**Detection regex (informational):**

```
^(CALL|PUT)\s+(\S+)\s+(\d{2}/\d{2}/\d{2})\s+([\d.]+)
```

If the Description matches this pattern, the transaction is an options trade. The `Symbol` field in the CSV contains the **underlying symbol** (e.g. `NVDA`), not the OCC option symbol. The full OCC option symbol should be derived from the parsed description fields.

**Important quirks:**
- Fields are separated by variable whitespace (multiple spaces used for alignment). The parser must use a regex or strip-and-split approach, not fixed-position parsing.
- The 2-digit year in expiry must be interpreted as 20YY (e.g. `26` → `2026`).
- Strike prices have three decimal places in the raw format but are monetary values — store as `Decimal` with 2 decimal places (e.g. `220.000` → `220.00`).
- Index options may use the weekly ticker variant (e.g. `SPXW` for weekly SPX options). The underlying symbol parsed from Description should be stored as-is.

---

### 3.3 Options Position Lifecycle

#### 3.3.1 Position Identity

A unique options contract is identified by: `(underlying_symbol, strike_price, expiry_date, option_type)`.

#### 3.3.2 Position Legs

A position can have **multiple open legs** (scale-in) and **multiple close legs** (partial or scaled-out close). The data model uses a `OptionsPositionLeg` join table rather than single FKs.

| Leg Role | Source Transaction Categories |
|---|---|
| `OPEN` | `OPTIONS_BUY_TO_OPEN`, `OPTIONS_SELL_TO_OPEN` |
| `CLOSE` | `OPTIONS_BUY_TO_CLOSE`, `OPTIONS_SELL_TO_CLOSE`, `OPTIONS_EXPIRED`, `OPTIONS_ASSIGNED`, `OPTIONS_EXERCISED` |

Position status rules:
- **OPEN:** total open quantity > total close quantity.
- **CLOSED:** total close quantity equals total open quantity.
- **PARTIALLY_CLOSED:** total close quantity > 0 but < total open quantity.
- Realized P&L is calculated on the closed portion only.

#### 3.3.3 Position Matching Algorithm (FIFO)

- The **oldest** open leg (by `transaction_date`) is matched to the **earliest** close leg for the same contract.
- Partial closes create a new position record for the unmatched open quantity.

#### 3.3.4 Special Close Events

- **Worthless expiry (`OPTIONS_EXPIRED`):** The close leg has price = $0.00 and commission = $0.00. The `Price $` field in the CSV is blank for expired options — the parser must default this to `0.00`.
- **Assignment (`OPTIONS_ASSIGNED`):** The options position is closed. A new `EquityPosition` record is created with `source = ASSIGNMENT` and `cost_basis = strike_price`. Assignment shares are **never merged** with existing equity positions for the same symbol; separate lot tracking is required to preserve cost basis integrity.
- **Exercise (`OPTIONS_EXERCISED`):** Same equity position creation logic as assignment; `source = EXERCISE`.

#### 3.3.5 Covered Call Identification

- `is_covered_call` is **stamped** on the `OptionsPosition` record at position-creation time.
- A short CALL position is considered covered if the user holds ≥ 100 shares per contract of the underlying at position creation time.
- Equity holdings are determined by querying `EquityPosition` records (which are created for **both** `EQUITY_BUY` and `OPTIONS_ASSIGNED`/`OPTIONS_EXERCISED` events — see Section 3.4).
- **Re-evaluation trigger:** After any upload containing `EQUITY_BUY`, `OPTIONS_ASSIGNED`, or `OPTIONS_EXERCISED` transactions, `is_covered_call` is re-evaluated for all OPEN short CALL positions in the same underlying.

#### 3.3.6 Rolling Positions

A roll (closing an existing position and opening a new one in the same underlying) is represented as two independent positions: a CLOSED position (the buy-to-close leg) and a new OPEN position (the sell-to-open leg). The system does not automatically link rolled positions in v0.1. A `parent_position_id` FK is reserved for v1.0 roll-chain tracking.

#### 3.3.7 Multi-Leg Strategies

In v0.1, multi-leg strategies (spreads, condors, straddles) are tracked as **individual single-leg positions**. Each leg is independently matched and P&L is independently calculated. Strategy-level grouping is deferred to v1.0.

---

### 3.4 Equity Position Lifecycle

- An `EquityPosition` record is created for every `EQUITY_BUY`, `OPTIONS_ASSIGNED`, and `OPTIONS_EXERCISED` transaction.
- `source` field values: `PURCHASE`, `ASSIGNMENT`, `EXERCISE`.
- When an `EQUITY_SELL` transaction is processed and a matching OPEN `EquityPosition` exists (same symbol, sufficient quantity):
  - The position's quantity is reduced.
  - If quantity reaches zero, `status` changes to `CLOSED` and `equity_realized_pnl` is calculated.
  - Equity P&L = `(sell_price − cost_basis_per_share) × quantity_sold`.
- Equity `EquityPosition` records participate in covered call detection but **not** in options P&L calculations.

---

### 3.5 P&L Calculation

#### 3.5.1 Sign Convention

All transaction amounts use **cash-flow sign convention**: credits to the account are positive, debits are negative.

- `SELL_TO_OPEN`: premium received → **positive** Open Amount
- `BUY_TO_OPEN`: premium paid → **negative** Open Amount
- `SELL_TO_CLOSE`: proceeds received → **positive** Close Amount
- `BUY_TO_CLOSE`: cost to close → **negative** Close Amount
- `OPTIONS_EXPIRED` close: price = $0.00, commission = $0.00

#### 3.5.2 Formula

```
Open Amount  = open_price × 100 × open_quantity  (signed per convention above)
Close Amount = close_price × 100 × close_quantity (signed per convention above)
Realized P&L = Open Amount + Close Amount − |open_commission| − |close_commission|
```

For partially closed positions, P&L is calculated on the closed portion using FIFO-matched quantities.

**Example — Covered call:**
> Sold 1 call at $2.00 premium → Open Amount = +$200.
> Bought back at $0.50 → Close Amount = −$50.
> Commissions: $1.00 open + $1.00 close.
> Realized P&L = $200 − $50 − $1 − $1 = **+$148**

**Example — Long call expiry (worthless):**
> Bought 1 call at $1.50 → Open Amount = −$150.
> Expired worthless → Close Amount = $0.
> Commission: $1.00 open + $0.00 close.
> Realized P&L = −$150 + $0 − $1 = **−$151**

#### 3.5.3 Commission Scope

`commission` on a `Transaction` record stores the **total broker-reported commission including all regulatory fees** (SEC fee, FINRA TAF, etc.) for that single transaction. The application does not break down fee sub-components.

#### 3.5.4 Aggregation

P&L is aggregated and displayed:
- Per position (individual trade P&L)
- By underlying symbol
- By calendar month and year
- Open positions show current cost basis but no realized P&L.

---

### 3.6 Audit Trail

- Every transaction record stores a reference (`upload_id`) to its source upload.
- Users can navigate from any position or P&L figure back to originating transactions and the source upload file.
- Deleted or superseded records are **soft-deleted** and retained for audit purposes; they are never permanently removed.

---

### 3.7 User Interface

- **Dashboard:** Summary cards — total realized P&L, open position count, closed position count, recent uploads.
- **Upload Page:** File-picker or drag-and-drop CSV upload (broker is implicitly E*TRADE in MVP1), progress feedback, post-upload summary (rows parsed, options found, duplicates detected, internal transfers filtered, parse errors).
- **Transactions Page:** Filterable, sortable, paginated table of all transactions with category, status, and upload link.
- **Positions Page:** Filterable, sortable, paginated table of options positions with status and realized P&L for closed positions.
- **Upload History Page:** List of all uploads with timestamp, file name, broker, row counts, and per-upload breakdown.

---

## 4. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Test coverage | 100% line and branch coverage enforced in CI for both backend and frontend |
| Testing approach | Strict TDD — tests written before implementation |
| Performance | Upload processing for files up to 10,000 rows must complete in under 10 seconds |
| File size limit | Maximum upload file size: 10MB and 10,000 rows |
| Security | No authentication in v0.1 (single-user local deployment); JWT-based auth planned for v1.0 |
| Portability | Full stack runs via `docker compose up` with no external dependencies |
| Observability | Structured JSON logging to stdout; `LOG_LEVEL` configurable via environment variable (default: `INFO`) |
| Indexing | Required DB indexes: `transactions(upload_id, symbol, category, transaction_date)`, `options_positions(underlying, status, expiry)` |
| API pagination | All list endpoints support `offset`/`limit` pagination (max 500 items per page) |

---

## 5. Technical Architecture

### 5.1 Stack

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | Angular (latest LTS) | Component-based SPA, strong TypeScript support |
| Backend | Python + FastAPI | Async-capable, automatic OpenAPI docs, strong typing via Pydantic |
| Database | PostgreSQL 16 | ACID compliance, strong JSONB support for raw transaction data |
| DB Migrations | Alembic | De-facto standard for SQLAlchemy-based projects |
| ORM | SQLAlchemy 2.x (async) | Full async support, integrates with Alembic |
| Containerisation | Docker + Docker Compose | Single-command local deployment |
| CI | GitHub Actions | Native GitHub integration |

### 5.2 Backend Tooling

| Tool | Purpose |
|---|---|
| **Poetry** | Dependency management and virtual environment |
| **Ruff** | Linting and formatting (replaces flake8, isort, black) |
| **mypy** | Static type checking |
| **pytest** | Test runner |
| **pytest-cov** | Coverage reporting (enforces 100% gate) |
| **pytest-asyncio** | Async test support |
| **httpx** | Async HTTP client for FastAPI test client |
| **factory-boy** | Test data factories |
| **Alembic** | Schema migration management |

### 5.3 Frontend Tooling

| Tool | Purpose |
|---|---|
| **Angular CLI** | Project scaffolding and build |
| **ESLint** + `@angular-eslint` | Linting |
| **Prettier** | Code formatting |
| **Jest** + `jest-preset-angular` | Unit test runner (replaces Karma) |
| **@angular/cdk** | Component utilities |

### 5.4 Project Structure (Target)

```
options-tracker/
├── PRD.md
├── docker-compose.yml
├── .env.example
├── .github/
│   └── workflows/
│       ├── backend-ci.yml
│       └── frontend-ci.yml
├── backend/
│   ├── pyproject.toml          # Poetry config, Ruff config, mypy config
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── uploads.py
│   │   │       ├── transactions.py
│   │   │       └── positions.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── parser/         # Broker adapters (etrade, ...)
│   │   │   ├── classifier.py   # Transaction classification
│   │   │   ├── deduplicator.py # Composite-key dedup logic
│   │   │   ├── matcher.py      # FIFO open/close matching
│   │   │   └── pnl.py          # P&L calculation
│   │   └── repositories/       # DB access layer
│   └── tests/
│       ├── unit/
│       └── integration/
└── frontend/
    ├── angular.json
    ├── package.json
    ├── src/
    │   ├── app/
    │   │   ├── core/
    │   │   ├── features/
    │   │   │   ├── dashboard/
    │   │   │   ├── upload/
    │   │   │   ├── transactions/
    │   │   │   └── positions/
    │   │   └── shared/
    │   └── environments/
    └── jest.config.ts
```

### 5.5 Domain Models

```
Upload
  id, filename, broker, uploaded_at, row_count, options_count,
  duplicate_count, parse_error_count, internal_transfer_count,
  status (ACTIVE | SOFT_DELETED)

RawTransaction
  id, upload_id (FK→Upload), raw_data (JSONB),
  is_internal_transfer (boolean, default false),
  status (ACTIVE | DUPLICATE | POSSIBLE_DUPLICATE | PARSE_ERROR)

Transaction
  id, raw_transaction_id (FK→RawTransaction), upload_id (FK→Upload),
  broker_transaction_id (nullable),  -- always null for E*TRADE; reserved for future brokers
  broker_name,
  trade_date, transaction_date, settlement_date (nullable),
  symbol, option_symbol,
  strike (nullable), expiry (nullable), option_type (CALL | PUT | null),
  action, quantity (positive integer), price (nullable), commission,
  amount,
  category (see Section 3.2), status (ACTIVE | SOFT_DELETED)

OptionsPosition
  id, underlying, option_symbol, strike, expiry, option_type,
  direction (LONG | SHORT),
  status (OPEN | PARTIALLY_CLOSED | CLOSED | EXPIRED | ASSIGNED | EXERCISED),
  realized_pnl (nullable decimal), is_covered_call (boolean),
  parent_position_id (FK→OptionsPosition, nullable — reserved for v1.0 rolls)

OptionsPositionLeg                         ← replaces single open/close FKs
  id, position_id (FK→OptionsPosition),
  transaction_id (FK→Transaction),
  leg_role (OPEN | CLOSE),
  quantity (positive integer)

EquityPosition
  id, symbol, quantity, cost_basis_per_share,
  source (PURCHASE | ASSIGNMENT | EXERCISE),
  assigned_position_id (FK→OptionsPosition, nullable),
  status (OPEN | CLOSED),
  closed_at (nullable datetime),
  equity_realized_pnl (nullable decimal),
  close_transaction_id (FK→Transaction, nullable)
```

### 5.6 E*TRADE CSV Adapter Specification

The E*TRADE adapter (`app/services/parser/etrade.py`) is responsible for transforming a raw E*TRADE CSV file into a list of `ParsedTransaction` objects.

**Parsing pipeline:**

1. **Preamble skip:** Read the file and skip rows 1–6. Identify the header row as row 7 (0-indexed row 6).
2. **Header validation:** Verify all 13 expected column headers are present. Raise `FileValidationError` if any are missing.
3. **Sentinel normalisation:** Replace all `--` values with `None` before further processing.
4. **Trailing row handling:** Skip any rows that are blank or do not parse as valid CSV records (the file may contain legal disclaimer text after the last transaction row).
5. **Date parsing:** Parse all date fields as `MM/DD/YY` → `datetime.date` using 2-digit year expansion (YY + 2000).
6. **Numeric parsing:** Parse `Quantity #`, `Price $`, `Amount $`, `Commission` as `Decimal`. Blank fields become `None` (not zero) except `Commission` which defaults to `Decimal('0.00')` when blank.
7. **Quantity sign normalisation:** Store the absolute value of `Quantity #` as `quantity` on the `ParsedTransaction`. Record the original sign separately to inform direction classification.
8. **Options description parsing:** For any row where `Activity Type` is one of `Sold Short`, `Bought To Cover`, `Bought To Open`, `Sold To Close`, `Option Expired`, `Option Assigned`, apply the options description regex (Section 3.2.2) to extract `option_type`, `underlying`, `expiry`, `strike`.
9. **Activity type classification:** Map `Activity Type` to internal `category` per the table in Section 3.2.1.
10. **Internal transfer detection:** For `Transfer` rows, detect paired legs (same date, equal-and-opposite amount, same description) and mark both with `is_internal_transfer = true`.
11. **Deduplication check:** Compute the Tier 2 composite key and query for existing matching `RawTransaction` records.

**`ParsedTransaction` fields produced by the adapter:**

```python
@dataclass
class ParsedTransaction:
    trade_date: date
    transaction_date: date
    settlement_date: date | None
    activity_type_raw: str          # original CSV value, preserved for audit
    description: str
    symbol: str | None
    cusip: str | None
    quantity: Decimal | None        # always positive (absolute value)
    price: Decimal | None
    amount: Decimal | None
    commission: Decimal
    category: TransactionCategory
    option_type: OptionType | None  # CALL | PUT | None
    underlying: str | None
    expiry: date | None
    strike: Decimal | None
    is_internal_transfer: bool
```

---

## 6. API Design

All list endpoints support `?offset=0&limit=100` pagination (max `limit=500`).

| Method | Path | Query Parameters | Description |
|---|---|---|---|
| `POST` | `/api/v1/uploads` | — | Upload a CSV file (multipart form; broker field not required in MVP1 — implicitly E*TRADE) |
| `GET` | `/api/v1/uploads` | `date_from`, `date_to`, `offset`, `limit` | List all uploads |
| `GET` | `/api/v1/uploads/{id}` | — | Get upload detail with row count breakdown |
| `DELETE` | `/api/v1/uploads/{id}` | — | Soft-delete upload with cascade |
| `GET` | `/api/v1/transactions` | `category`, `status`, `symbol`, `upload_id`, `date_from`, `date_to`, `offset`, `limit`, `sort_by`, `sort_dir` | List transactions |
| `GET` | `/api/v1/positions` | `status`, `underlying`, `option_type`, `expiry_from`, `expiry_to`, `offset`, `limit`, `sort_by`, `sort_dir` | List options positions |
| `GET` | `/api/v1/positions/{id}` | — | Position detail with all legs and P&L breakdown |
| `GET` | `/api/v1/pnl/summary` | `period` (month \| year), `underlying` | Aggregated realized P&L |

---

## 7. CI/CD Pipeline

### 7.1 Backend CI (`backend-ci.yml`)

Triggers: push and pull_request on `main` and `develop`.

Steps:
1. Checkout code
2. Set up Python via Poetry
3. `ruff check` — linting
4. `ruff format --check` — formatting
5. `mypy app` — type checking
6. `pytest --cov=app --cov-fail-under=100 --cov-branch` — tests + 100% coverage gate
7. Upload coverage report as artifact

### 7.2 Frontend CI (`frontend-ci.yml`)

Triggers: push and pull_request on `main` and `develop`.

Steps:
1. Checkout code
2. `npm ci`
3. `ng lint` — ESLint
4. `npx prettier --check .` — formatting
5. `npx jest --coverage --coverageThreshold='{"global":{"lines":100,"branches":100,"functions":100,"statements":100}}'` — tests + 100% coverage gate
6. `ng build --configuration production` — build gate

### 7.3 Docker Build CI

Steps:
1. `docker compose build` — verify all images build successfully

---

## 8. Local Development Setup

```bash
# Clone and start everything
git clone <repo>
cd options-tracker
cp .env.example .env
docker compose up --build

# Services available at:
#   Frontend:  http://localhost:4200
#   Backend:   http://localhost:8000
#   API docs:  http://localhost:8000/docs
#   DB:        localhost:5432
```

`.env.example` will be provided with all required environment variables including `LOG_LEVEL`, `DATABASE_URL`, and `POSTGRES_*` credentials.

---

## 9. Out of Scope (v0.1)

- Multi-user authentication and authorisation (planned for v1.0)
- Broker API integrations (manual CSV upload only)
- Real-time options pricing / Greeks
- Tax lot accounting (FIFO/LIFO/SpecID)
- Roll-chain tracking across multiple positions (`parent_position_id`)
- Multi-leg strategy grouping (spreads, condors, iron flies)
- Mobile app
- Notifications / alerts
- Broker auto-detection from file contents

---

## 10. Resolved Decisions

| # | Decision | Resolution |
|---|---|---|
| D1 | Broker format for v0.1 | **E*TRADE CSV** (see D17); broker adapter pattern for extensibility |
| D2 | Deduplication key | **Tier 2 composite key only** for E*TRADE (no broker transaction ID in this format — see D16); `POSSIBLE_DUPLICATE` status for ambiguous matches |
| D3 | Multi-leg strategies | Individual legs tracked independently in v0.1; strategy grouping deferred to v1.0 |
| D4 | Assignment equity tracking | Always create separate `EquityPosition` per lot; never merge; cost basis = strike price |
| D5 | Covered call identification | Stamped at creation time; re-evaluated after any upload affecting equity holdings |
| D6 | Position data model | `OptionsPositionLeg` join table (not single FKs) to support scale-in and partial close |
| D7 | Matching algorithm | FIFO — oldest open matched to earliest close |
| D8 | Quantity sign | Always positive on `Transaction`; direction encoded in `category`; CSV signed quantity used only during parsing |
| D9 | `EquityPosition` for EQUITY_BUY | Yes — created for purchases, assignments, and exercises; required for covered call detection |
| D10 | Upload soft-delete cascade | Yes — with revert-to-open rule for positions straddling two uploads |
| D11 | Worthless expiry P&L | Close price = $0.00, commission = $0.00; blank `Price $` field in CSV must be defaulted to 0.00 |
| D12 | `OPTIONS_EXERCISED` category | Added to taxonomy |
| D13 | `INTEREST`, `FEE`, `JOURNAL` categories | Added to taxonomy |
| D14 | Max upload file size | 10MB and 10,000 rows |
| D15 | Logging | Structured JSON to stdout; `LOG_LEVEL` env var (default: `INFO`) |
| D16 | No broker transaction ID in E*TRADE format | E*TRADE CSV does not include a unique transaction ID field. Deduplication uses composite key only: `(trade_date, transaction_date, settlement_date, activity_type, description, symbol, quantity, price, amount, commission)` |
| D17 | MVP1 broker selection: E*TRADE CSV export only | The `broker` field is not required in the upload API for MVP1; it is implicitly E*TRADE. Multi-broker support requires the adapter pattern already in the architecture but is deferred to v0.2. |
| D18 | Internal transfer filtering | Paired `TRNSFR` rows (Activity Type = Transfer, description starts with `TRNSFR`) are stored as `RawTransaction` but excluded from analytics. Orphaned (unpaired) `TRNSFR` rows are flagged as `PARSE_ERROR`. |
| D19 | `Sold Short` / `Bought To Cover` disambiguation | These CSV activity types are used by E*TRADE for both equity short selling and short options. Description-field regex matching (Section 3.2.2) is the authoritative discriminator. |
| D20 | `Option Expired` price field | The `Price $` field is blank in the CSV for expired options. The parser must default this to `Decimal('0.00')` — it is not a parse error. |
| D21 | Fractional share transactions | The CSV contains fractional share quantities (e.g. `0.213`, `1.818`). `Quantity` on `Transaction` records should be stored as `Decimal`, not integer, to accommodate fractional equity purchases. **This supersedes the "always positive integer" statement for equity transactions** — options contract quantities remain whole numbers. |

---

## 11. Remaining Open Questions

1. **Equity P&L in v0.1:** Should `EQUITY_SELL` close `EquityPosition` records and calculate equity realized P&L in v0.1, or defer to v1.0? *(Recommended: include as "Should Have")*
2. **Partial close display:** When a position is `PARTIALLY_CLOSED`, should the UI show one row per leg pair or one row per position with a breakdown drawer?
3. **P&L summary period:** Should the P&L summary support both month and year aggregation simultaneously, or is one at a time sufficient for v0.1?
4. **DRIP dividend handling:** Dividend reinvestment (DRIP) transactions in the CSV appear as a paired pattern: one `Dividend` row with a negative amount (debit — shares purchased) and a companion `Dividend` row with a positive amount (credit — cash dividend). Should these be linked and treated as a net-zero cash event, or tracked independently? Currently both are classified as `DIVIDEND`. Clarification needed.
5. **`Bought To Open` / `Sold To Close` activity types:** These are also present in the CSV (in addition to `Sold Short` / `Bought To Cover`) and map unambiguously to `OPTIONS_BUY_TO_OPEN` and `OPTIONS_SELL_TO_CLOSE` respectively. Confirm that both activity type variants should be supported (they appear to represent the same economic event via different E*TRADE order entry paths).
