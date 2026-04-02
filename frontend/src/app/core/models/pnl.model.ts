export type PnlPeriod = 'month' | 'year';

export type PnlGroupBy = 'period' | 'underlying';

export interface PnlPositionsParams {
  period: PnlPeriod;
  group_by: PnlGroupBy;
  period_label: string;
  underlying?: string;
}

export interface PnlPeriodEntry {
  period_label: string;
  options_pnl: string;
  equity_pnl: string;
  total_pnl: string;
}

export interface PnlSummary {
  period: string;
  group_by: string;
  items: PnlPeriodEntry[];
}

export interface PnlQueryParams {
  period?: PnlPeriod;
  underlying?: string;
  start_date?: string;
  end_date?: string;
  group_by?: PnlGroupBy;
}
