export type PnlPeriod = 'month' | 'year';

export interface PnlPeriodEntry {
  period_label: string;
  options_pnl: string;
  equity_pnl: string;
  total_pnl: string;
}

export interface PnlSummary {
  period: string;
  items: PnlPeriodEntry[];
}

export interface PnlQueryParams {
  period?: PnlPeriod;
  underlying?: string;
  start_date?: string;
  end_date?: string;
}
