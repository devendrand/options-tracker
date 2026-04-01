import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../api.config';
import { Transaction, TransactionQueryParams } from '../models/transaction.model';
import { PaginatedResponse } from '../models/pagination.model';

@Injectable({ providedIn: 'root' })
export class TransactionService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  getTransactions(params?: TransactionQueryParams): Observable<PaginatedResponse<Transaction>> {
    let httpParams = new HttpParams();
    if (params) {
      if (params.offset !== undefined) {
        httpParams = httpParams.set('offset', String(params.offset));
      }
      if (params.limit !== undefined) {
        httpParams = httpParams.set('limit', String(params.limit));
      }
      if (params.symbol !== undefined) {
        httpParams = httpParams.set('symbol', params.symbol);
      }
      if (params.category?.length) {
        params.category.forEach((c) => (httpParams = httpParams.append('category', c)));
      }
      if (params.dedup_status?.length) {
        params.dedup_status.forEach((s) => (httpParams = httpParams.append('dedup_status', s)));
      }
      if (params.start_date !== undefined) {
        httpParams = httpParams.set('start_date', params.start_date);
      }
      if (params.end_date !== undefined) {
        httpParams = httpParams.set('end_date', params.end_date);
      }
    }
    return this.http.get<PaginatedResponse<Transaction>>(`${this.baseUrl}/transactions`, {
      params: httpParams,
    });
  }
}
