export type UploadStatus = 'ACTIVE' | 'SOFT_DELETED';

export interface Upload {
  id: string;
  filename: string;
  status: UploadStatus;
  broker: string;
  row_count: number | null;
  options_count: number | null;
  duplicate_count: number | null;
  possible_duplicate_count: number | null;
  parse_error_count: number | null;
  internal_transfer_count: number | null;
  uploaded_at: string;
}

export interface UploadListResponse {
  items: Upload[];
  total: number;
  offset: number;
  limit: number;
}
