import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../api.config';
import { PnlSummary, PnlQueryParams, PnlPositionsParams } from '../models/pnl.model';
import { PositionListResponse } from '../models/position.model';

@Injectable({ providedIn: 'root' })
export class PnlService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  getSummary(params?: PnlQueryParams): Observable<PnlSummary> {
    let httpParams = new HttpParams();
    if (params) {
      if (params.period !== undefined) {
        httpParams = httpParams.set('period', params.period);
      }
      if (params.underlying !== undefined) {
        httpParams = httpParams.set('underlying', params.underlying);
      }
      if (params.start_date !== undefined) {
        httpParams = httpParams.set('start_date', params.start_date);
      }
      if (params.end_date !== undefined) {
        httpParams = httpParams.set('end_date', params.end_date);
      }
      if (params.group_by !== undefined) {
        httpParams = httpParams.set('group_by', params.group_by);
      }
    }
    return this.http.get<PnlSummary>(`${this.baseUrl}/pnl/summary`, {
      params: httpParams,
    });
  }

  getPositionsForBucket(params: PnlPositionsParams): Observable<PositionListResponse> {
    let httpParams = new HttpParams()
      .set('period', params.period)
      .set('group_by', params.group_by)
      .set('period_label', params.period_label);
    if (params.underlying !== undefined) {
      httpParams = httpParams.set('underlying', params.underlying);
    }
    return this.http.get<PositionListResponse>(`${this.baseUrl}/pnl/positions`, {
      params: httpParams,
    });
  }
}
