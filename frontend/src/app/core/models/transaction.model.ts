export type TransactionCategory =
  | 'OPTIONS_SELL_TO_OPEN'
  | 'OPTIONS_BUY_TO_OPEN'
  | 'OPTIONS_BUY_TO_CLOSE'
  | 'OPTIONS_SELL_TO_CLOSE'
  | 'OPTIONS_EXPIRED'
  | 'OPTIONS_ASSIGNED'
  | 'OPTIONS_EXERCISED'
  | 'EQUITY_BUY'
  | 'EQUITY_SELL'
  | 'DIVIDEND'
  | 'TRANSFER'
  | 'INTEREST'
  | 'FEE'
  | 'JOURNAL'
  | 'OTHER';

export interface Transaction {
  id: string;
  upload_id: string;
  broker_name: string;
  trade_date: string;
  transaction_date: string;
  settlement_date: string | null;
  symbol: string;
  option_symbol: string | null;
  strike: string | null;
  expiry: string | null;
  option_type: string | null;
  action: string;
  description: string | null;
  quantity: string;
  price: string | null;
  commission: string;
  amount: string;
  category: TransactionCategory;
  status: string;
  deleted_at: string | null;
}

export interface TransactionQueryParams {
  offset?: number;
  limit?: number;
  symbol?: string;
  category?: TransactionCategory[];
  status?: string[];
  start_date?: string;
  end_date?: string;
}
