export type OptionType = 'CALL' | 'PUT';
export type PositionStatus = 'OPEN' | 'CLOSED' | 'PARTIALLY_CLOSED';

export interface OptionsPositionLeg {
  id: string;
  position_id: string;
  transaction_id: string;
  leg_type: 'OPEN' | 'CLOSE';
  quantity: string;
  price: string;
  amount: string;
  commission: string;
  trade_date: string;
}

export interface OptionsPosition {
  id: string;
  underlying: string;
  option_type: OptionType;
  strike: string;
  expiry: string;
  status: PositionStatus;
  is_covered_call: boolean;
  realized_pnl: string | null;
  legs: OptionsPositionLeg[];
  created_at: string;
  updated_at: string;
}

export interface PositionQueryParams {
  offset?: number;
  limit?: number;
  underlying?: string;
  status?: PositionStatus;
  option_type?: OptionType;
}
