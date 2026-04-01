import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../api.config';
import { Upload, UploadListResponse } from '../models/upload.model';

@Injectable({ providedIn: 'root' })
export class UploadService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  getUploads(): Observable<UploadListResponse> {
    return this.http.get<UploadListResponse>(`${this.baseUrl}/uploads`);
  }

  getUpload(id: string): Observable<Upload> {
    return this.http.get<Upload>(`${this.baseUrl}/uploads/${id}`);
  }

  createUpload(file: File): Observable<Upload> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<Upload>(`${this.baseUrl}/uploads`, formData);
  }

  deleteUpload(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/uploads/${id}`);
  }
}
