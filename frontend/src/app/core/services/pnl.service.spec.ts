import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { PnlService } from './pnl.service';
import { API_BASE_URL } from '../api.config';
import { PnlSummary, PnlQueryParams, PnlGroupBy, PnlPositionsParams } from '../models/pnl.model';
import { PositionListResponse } from '../models/position.model';

const mockPnlSummary: PnlSummary = {
  period: 'month',
  group_by: 'period',
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

    it('should serialize group_by query param', (done) => {
      const params: PnlQueryParams = { group_by: 'underlying' as PnlGroupBy };

      service.getSummary(params).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.get('group_by')).toBe('underlying');
      req.flush(mockPnlSummary);
    });

    it('should serialize group_by=period_underlying query param', (done) => {
      service.getSummary({ group_by: 'period_underlying' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.get('group_by')).toBe('period_underlying');
      req.flush(mockPnlSummary);
    });

    it('should omit group_by when undefined', (done) => {
      service.getSummary({ period: 'year' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.has('group_by')).toBe(false);
      req.flush(mockPnlSummary);
    });

    it('should serialize closed_after param', (done) => {
      service.getSummary({ closed_after: '2026-01-01' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.get('closed_after')).toBe('2026-01-01');
      req.flush(mockPnlSummary);
    });

    it('should serialize closed_before param', (done) => {
      service.getSummary({ closed_before: '2026-12-31' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.get('closed_before')).toBe('2026-12-31');
      req.flush(mockPnlSummary);
    });

    it('should omit closed_after when undefined', (done) => {
      service.getSummary({ period: 'year' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/summary');
      expect(req.request.params.has('closed_after')).toBe(false);
      req.flush(mockPnlSummary);
    });
  });

  describe('getPositionsForBucket()', () => {
    const mockPositionListResponse: PositionListResponse = {
      total: 1,
      offset: 0,
      limit: 100,
      options_items: [
        {
          id: 'pos-1',
          underlying: 'SPX',
          option_symbol: 'SPX 2026-01-30 PUT 100',
          strike: '100',
          expiry: '2026-01-30',
          option_type: 'PUT',
          direction: 'LONG',
          status: 'CLOSED',
          realized_pnl: '500.00',
          is_covered_call: false,
        },
      ],
      equity_items: [],
    };

    it('should call GET /api/v1/pnl/positions with required params', (done) => {
      const params: PnlPositionsParams = {
        period: 'year',
        group_by: 'period',
        period_label: '2026',
      };

      service.getPositionsForBucket(params).subscribe({
        next: (response) => {
          expect(response).toEqual(mockPositionListResponse);
          done();
        },
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/positions');
      expect(req.request.method).toBe('GET');
      expect(req.request.params.get('period')).toBe('year');
      expect(req.request.params.get('group_by')).toBe('period');
      expect(req.request.params.get('period_label')).toBe('2026');
      req.flush(mockPositionListResponse);
    });

    it('should include underlying param when provided', (done) => {
      const params: PnlPositionsParams = {
        period: 'month',
        group_by: 'underlying',
        period_label: 'SPX',
        underlying: 'SPX',
      };

      service.getPositionsForBucket(params).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/positions');
      expect(req.request.params.get('underlying')).toBe('SPX');
      req.flush(mockPositionListResponse);
    });

    it('should omit underlying param when not provided', (done) => {
      const params: PnlPositionsParams = {
        period: 'year',
        group_by: 'period',
        period_label: '2026',
      };

      service.getPositionsForBucket(params).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/positions');
      expect(req.request.params.has('underlying')).toBe(false);
      req.flush(mockPositionListResponse);
    });

    it('should serialize closed_after and closed_before params', (done) => {
      const params: PnlPositionsParams = {
        period: 'year',
        group_by: 'underlying',
        period_label: 'SPX',
        closed_after: '2026-01-01',
        closed_before: '2026-12-31',
      };

      service.getPositionsForBucket(params).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/pnl/positions');
      expect(req.request.params.get('closed_after')).toBe('2026-01-01');
      expect(req.request.params.get('closed_before')).toBe('2026-12-31');
      req.flush(mockPositionListResponse);
    });
  });
});
