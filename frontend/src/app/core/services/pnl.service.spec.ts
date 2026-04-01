import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { PnlService } from './pnl.service';
import { API_BASE_URL } from '../api.config';
import { PnlSummary, PnlQueryParams } from '../models/pnl.model';

const mockPnlSummary: PnlSummary = {
  period: 'month',
  items: [
    { period_label: '2026-01', options_pnl: '500.00', equity_pnl: '0.00', total_pnl: '500.00' },
    { period_label: '2026-02', options_pnl: '750.00', equity_pnl: '0.00', total_pnl: '750.00' },
  ],
};

describe('PnlService', () => {
  let service: PnlService;
  let controller: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: '/api/v1' },
        PnlService,
      ],
    });
    service = TestBed.inject(PnlService);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    controller.verify();
  });

  describe('getSummary()', () => {
    it('should GET /api/v1/pnl/summary without params', (done) => {
      service.getSummary().subscribe({
        next: (summary) => {
          expect(summary).toEqual(mockPnlSummary);
          done();
        },
        error: done.fail,
      });

      const req = controller.expectOne('/api/v1/pnl/summary');
      expect(req.request.method).toBe('GET');
      req.flush(mockPnlSummary);
    });

    it('should serialize period query param', (done) => {
      const params: PnlQueryParams = { period: 'month' };

      service.getSummary(params).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.get('period')).toBe('month');
      req.flush(mockPnlSummary);
    });

    it('should serialize year period query param', (done) => {
      service.getSummary({ period: 'year' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.get('period')).toBe('year');
      req.flush(mockPnlSummary);
    });

    it('should serialize underlying query param', (done) => {
      service.getSummary({ underlying: 'NVDA' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.get('underlying')).toBe('NVDA');
      req.flush(mockPnlSummary);
    });

    it('should serialize start_date and end_date query params', (done) => {
      service.getSummary({ start_date: '2026-01-01', end_date: '2026-03-31' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.get('start_date')).toBe('2026-01-01');
      expect(req.request.params.get('end_date')).toBe('2026-03-31');
      req.flush(mockPnlSummary);
    });

    it('should omit undefined params', (done) => {
      service.getSummary({ period: undefined, start_date: '2026-01-01' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.has('period')).toBe(false);
      expect(req.request.params.get('start_date')).toBe('2026-01-01');
      req.flush(mockPnlSummary);
    });
  });
});
