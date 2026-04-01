export interface ApiError {
  status: number;
  message: string;
  detail?: unknown;
}
