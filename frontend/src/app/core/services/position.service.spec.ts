import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { PositionService } from './position.service';
import { API_BASE_URL } from '../api.config';
import { OptionsPosition, PositionQueryParams } from '../models/position.model';
import { PaginatedResponse } from '../models/pagination.model';

const mockPosition: OptionsPosition = {
  id: 'pos-1',
  underlying: 'AAPL',
  option_type: 'CALL',
  strike: '200.00',
  expiry: '2026-03-15',
  status: 'CLOSED',
  is_covered_call: false,
  realized_pnl: '350.00',
  legs: [],
  created_at: '2026-03-01T10:00:00Z',
  updated_at: '2026-03-15T10:00:00Z',
};

const mockPaginatedResponse: PaginatedResponse<OptionsPosition> = {
  items: [mockPosition],
  total: 1,
  offset: 0,
  limit: 100,
};

describe('PositionService', () => {
  let service: PositionService;
  let controller: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: '/api/v1' },
        PositionService,
      ],
    });
    service = TestBed.inject(PositionService);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    controller.verify();
  });

  describe('getPositions()', () => {
    it('should GET /api/v1/positions without params and return paginated response', (done) => {
      service.getPositions().subscribe({
        next: (res) => {
          expect(res).toEqual(mockPaginatedResponse);
          done();
        },
        error: done.fail,
      });

      const req = controller.expectOne('/api/v1/positions');
      expect(req.request.method).toBe('GET');
      req.flush(mockPaginatedResponse);
    });

    it('should serialize underlying query param', (done) => {
      const params: PositionQueryParams = { underlying: 'AAPL' };

      service.getPositions(params).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/positions');
      expect(req.request.params.get('underlying')).toBe('AAPL');
      req.flush(mockPaginatedResponse);
    });

    it('should serialize status query param', (done) => {
      service.getPositions({ status: 'OPEN' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/positions');
      expect(req.request.params.get('status')).toBe('OPEN');
      req.flush(mockPaginatedResponse);
    });

    it('should serialize option_type query param', (done) => {
      service.getPositions({ option_type: 'PUT' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/positions');
      expect(req.request.params.get('option_type')).toBe('PUT');
      req.flush(mockPaginatedResponse);
    });

    it('should serialize offset and limit query params', (done) => {
      service.getPositions({ offset: 0, limit: 50 }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/positions');
      expect(req.request.params.get('offset')).toBe('0');
      expect(req.request.params.get('limit')).toBe('50');
      req.flush(mockPaginatedResponse);
    });

    it('should omit undefined params', (done) => {
      service.getPositions({ underlying: undefined, limit: 25 }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/positions');
      expect(req.request.params.has('underlying')).toBe(false);
      expect(req.request.params.get('limit')).toBe('25');
      req.flush(mockPaginatedResponse);
    });
  });

  describe('getPosition(id)', () => {
    it('should GET /api/v1/positions/{id} and return a single position', (done) => {
      service.getPosition('pos-1').subscribe({
        next: (pos) => {
          expect(pos).toEqual(mockPosition);
          done();
        },
        error: done.fail,
      });

      const req = controller.expectOne('/api/v1/positions/pos-1');
      expect(req.request.method).toBe('GET');
      req.flush(mockPosition);
    });
  });
});
