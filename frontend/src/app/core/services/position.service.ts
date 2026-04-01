import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../api.config';
import { OptionsPosition, PositionQueryParams } from '../models/position.model';
import { PaginatedResponse } from '../models/pagination.model';

@Injectable({ providedIn: 'root' })
export class PositionService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  getPositions(params?: PositionQueryParams): Observable<PaginatedResponse<OptionsPosition>> {
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
      if (params.option_type !== undefined) {
        httpParams = httpParams.set('option_type', params.option_type);
      }
    }
    return this.http.get<PaginatedResponse<OptionsPosition>>(`${this.baseUrl}/positions`, {
      params: httpParams,
    });
  }

  getPosition(id: string): Observable<OptionsPosition> {
    return this.http.get<OptionsPosition>(`${this.baseUrl}/positions/${id}`);
  }
}
