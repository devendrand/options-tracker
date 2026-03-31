# OQ3: P&L Summary Period Aggregation

**Question:** Should the P&L summary support both month and year aggregation simultaneously, or is one at a time sufficient for v0.1?

**Resolution:** **One at a time is sufficient for v0.1.** The `?period=month|year` query parameter approach already specified in the API is the correct design.

**Rationale:**
Simultaneous display (e.g. a side-by-side monthly + annual breakdown on one screen) is a reporting feature with non-trivial UI layout complexity. For a v0.1 single-user local tool, the user can switch between views with a tab or toggle control. The data contract is already designed for one-at-a-time via `GET /api/v1/pnl/summary?period=month|year&underlying=...`.

Showing both simultaneously would require either two separate API calls on the summary page (acceptable) or a new combined endpoint (scope creep). For an MVP focused on correctness and data integrity, one-at-a-time is the right tradeoff.

**Implementation recommendation for the UI:** Add a period toggle (Month / Year) on the P&L summary page. The selected period fires a single API call. Default to `year` on first load to give the broadest view.

**Impact on implementation:**
- No change to API — `?period=month|year` is already specified
- Frontend: period toggle control (radio buttons or segmented control) above the P&L table
- The response format should include a sorted array of `{period_label, options_pnl, equity_pnl, total_pnl}` objects — the backend aggregation must group by the correct time bucket (calendar month or calendar year of `transaction_date`)
- No additional API endpoints needed
