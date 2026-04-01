import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { PositionService } from './position.service';
import { API_BASE_URL } from '../api.config';
import {
  OptionsPosition,
  OptionsPositionDetail,
  PositionListResponse,
} from '../models/position.model';

const mockOptionsPosition: OptionsPosition = {
  id: 'pos-1',
  underlying: 'AAPL',
  option_symbol: 'AAPL240119C00200000',
  strike: '200.00',
  expiry: '2026-03-15',
  option_type: 'CALL',
  direction: 'SHORT',
  status: 'CLOSED',
  is_covered_call: false,
  realized_pnl: '350.00',
};

const mockListResponse: PositionListResponse = {
  total: 1,
  offset: 0,
  limit: 100,
  options_items: [mockOptionsPosition],
  equity_items: [],
};

const mockDetail: OptionsPositionDetail = {
  ...mockOptionsPosition,
  legs: [],
  total_realized_pnl: '350.00',
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
    it('should GET /api/v1/positions without params and return PositionListResponse', (done) => {
      service.getPositions().subscribe({
        next: (res) => {
          expect(res).toEqual(mockListResponse);
          done();
        },
        error: done.fail,
      });

      const req = controller.expectOne('/api/v1/positions');
      expect(req.request.method).toBe('GET');
      req.flush(mockListResponse);
    });

    it('should serialize underlying query param', (done) => {
      service.getPositions({ underlying: 'AAPL' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/positions');
      expect(req.request.params.get('underlying')).toBe('AAPL');
      req.flush(mockListResponse);
    });

    it('should serialize status query param', (done) => {
      service.getPositions({ status: 'OPEN' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/positions');
      expect(req.request.params.get('status')).toBe('OPEN');
      req.flush(mockListResponse);
    });

    it('should serialize asset_type query param', (done) => {
      service.getPositions({ asset_type: 'options' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/positions');
      expect(req.request.params.get('asset_type')).toBe('options');
      req.flush(mockListResponse);
    });

    it('should serialize offset and limit query params', (done) => {
      service.getPositions({ offset: 0, limit: 50 }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/positions');
      expect(req.request.params.get('offset')).toBe('0');
      expect(req.request.params.get('limit')).toBe('50');
      req.flush(mockListResponse);
    });

    it('should omit undefined params', (done) => {
      service.getPositions({ underlying: undefined, limit: 25 }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/positions');
      expect(req.request.params.has('underlying')).toBe(false);
      expect(req.request.params.get('limit')).toBe('25');
      req.flush(mockListResponse);
    });
  });

  describe('getPosition(id)', () => {
    it('should GET /api/v1/positions/{id} and return OptionsPositionDetail', (done) => {
      service.getPosition('pos-1').subscribe({
        next: (pos) => {
          expect(pos).toEqual(mockDetail);
          done();
        },
        error: done.fail,
      });

      const req = controller.expectOne('/api/v1/positions/pos-1');
      expect(req.request.method).toBe('GET');
      req.flush(mockDetail);
    });
  });
});
