import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { UploadService } from './upload.service';
import { API_BASE_URL } from '../api.config';
import { Upload, UploadListResponse } from '../models/upload.model';

const mockUpload: Upload = {
  id: 'abc123',
  filename: 'trades.csv',
  status: 'ACTIVE',
  broker: 'ETRADE',
  row_count: 42,
  options_count: 10,
  duplicate_count: 2,
  possible_duplicate_count: 1,
  parse_error_count: 0,
  internal_transfer_count: 3,
  uploaded_at: '2026-03-15T10:00:00Z',
};

const mockListResponse: UploadListResponse = {
  items: [mockUpload],
  total: 1,
  offset: 0,
  limit: 100,
};

describe('UploadService', () => {
  let service: UploadService;
  let controller: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: '/api/v1' },
        UploadService,
      ],
    });
    service = TestBed.inject(UploadService);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    controller.verify();
  });

  describe('getUploads()', () => {
    it('should GET /api/v1/uploads and return a paginated list response', (done) => {
      service.getUploads().subscribe({
        next: (res) => {
          expect(res).toEqual(mockListResponse);
          done();
        },
        error: done.fail,
      });

      const req = controller.expectOne('/api/v1/uploads');
      expect(req.request.method).toBe('GET');
      req.flush(mockListResponse);
    });
  });

  describe('getUpload(id)', () => {
    it('should GET /api/v1/uploads/{id} and return a single upload', (done) => {
      service.getUpload('abc123').subscribe({
        next: (upload) => {
          expect(upload).toEqual(mockUpload);
          done();
        },
        error: done.fail,
      });

      const req = controller.expectOne('/api/v1/uploads/abc123');
      expect(req.request.method).toBe('GET');
      req.flush(mockUpload);
    });
  });

  describe('createUpload(file)', () => {
    it('should POST /api/v1/uploads with multipart/form-data and return the created upload', (done) => {
      const file = new File(['col1,col2\nval1,val2'], 'trades.csv', { type: 'text/csv' });

      service.createUpload(file).subscribe({
        next: (upload) => {
          expect(upload).toEqual(mockUpload);
          done();
        },
        error: done.fail,
      });

      const req = controller.expectOne('/api/v1/uploads');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toBeInstanceOf(FormData);
      const formData = req.request.body as FormData;
      expect(formData.get('file')).toBe(file);
      req.flush(mockUpload);
    });
  });

  describe('deleteUpload(id)', () => {
    it('should DELETE /api/v1/uploads/{id}', (done) => {
      service.deleteUpload('abc123').subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne('/api/v1/uploads/abc123');
      expect(req.request.method).toBe('DELETE');
      req.flush(null);
    });
  });
});
