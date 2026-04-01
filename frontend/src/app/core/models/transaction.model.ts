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
  trade_date: string;
  transaction_date: string;
  settlement_date: string | null;
  activity_type: string;
  description: string;
  symbol: string | null;
  quantity: string | null;
  price: string | null;
  amount: string;
  commission: string;
  category: TransactionCategory;
  is_internal_transfer: boolean;
  dedup_status: string;
  created_at: string;
}

export interface TransactionQueryParams {
  offset?: number;
  limit?: number;
  symbol?: string;
  category?: TransactionCategory[];
  dedup_status?: string[];
  start_date?: string;
  end_date?: string;
}
