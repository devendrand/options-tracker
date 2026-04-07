export type OptionType = 'CALL' | 'PUT';
export type PositionDirection = 'LONG' | 'SHORT';
export type OptionsPositionStatus =
  | 'OPEN'
  | 'PARTIALLY_CLOSED'
  | 'CLOSED'
  | 'EXPIRED'
  | 'ASSIGNED'
  | 'EXERCISED';
export type EquityPositionStatus = 'OPEN' | 'CLOSED';
export type EquityPositionSource = 'PURCHASE' | 'ASSIGNMENT' | 'EXERCISE';

export interface OptionsPositionLeg {
  id: string;
  transaction_id: string;
  leg_role: 'OPEN' | 'CLOSE';
  quantity: string;
  trade_date: string;
  price: string | null;
  amount: string;
  commission: string;
}

export interface OptionsPosition {
  id: string;
  underlying: string;
  option_symbol: string;
  strike: string;
  expiry: string;
  option_type: OptionType;
  direction: PositionDirection;
  status: OptionsPositionStatus;
  realized_pnl: string | null;
  is_covered_call: boolean;
  opened_at: string | null;
  closed_at: string | null;
}

export interface OptionsPositionDetail extends OptionsPosition {
  legs: OptionsPositionLeg[];
  total_realized_pnl: string | null;
}

export interface EquityPosition {
  id: string;
  symbol: string;
  quantity: string;
  cost_basis_per_share: string;
  status: EquityPositionStatus;
  source: EquityPositionSource;
  equity_realized_pnl: string | null;
  closed_at: string | null;
}

export interface PositionListResponse {
  total: number;
  offset: number;
  limit: number;
  options_items: OptionsPosition[];
  equity_items: EquityPosition[];
}

export interface PositionQueryParams {
  offset?: number;
  limit?: number;
  underlying?: string;
  status?: OptionsPositionStatus;
  asset_type?: 'options' | 'equity' | 'all';
}
