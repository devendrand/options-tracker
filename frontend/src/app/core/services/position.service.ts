import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../api.config';
import {
  OptionsPositionDetail,
  PositionListResponse,
  PositionQueryParams,
} from '../models/position.model';

@Injectable({ providedIn: 'root' })
export class PositionService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  getPositions(params?: PositionQueryParams): Observable<PositionListResponse> {
    let httpParams = new HttpParams();
    if (params) {
      if (params.offset !== undefined) {
        httpParams = httpParams.set('offset', String(params.offset));
      }
      if (params.limit !== undefined) {
        httpParams = httpParams.set('limit', String(params.limit));
      }
      if (params.underlying !== undefined) {
        httpParams = httpParams.set('underlying', params.underlying);
      }
      if (params.status !== undefined) {
        httpParams = httpParams.set('status', params.status);
      }
      if (params.asset_type !== undefined) {
        httpParams = httpParams.set('asset_type', params.asset_type);
      }
    }
    return this.http.get<PositionListResponse>(`${this.baseUrl}/positions`, {
      params: httpParams,
    });
  }

  getPosition(id: string): Observable<OptionsPositionDetail> {
    return this.http.get<OptionsPositionDetail>(`${this.baseUrl}/positions/${id}`);
  }
}
