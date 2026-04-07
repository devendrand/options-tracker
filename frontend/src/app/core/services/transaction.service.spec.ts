import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TransactionService } from './transaction.service';
import { API_BASE_URL } from '../api.config';
import { Transaction, TransactionQueryParams } from '../models/transaction.model';
import { PaginatedResponse } from '../models/pagination.model';

const mockTransaction: Transaction = {
  id: 'txn-1',
  upload_id: 'upload-1',
  broker_name: 'etrade',
  trade_date: '2026-03-01',
  transaction_date: '2026-03-01',
  settlement_date: '2026-03-03',
  symbol: 'AAPL',
  option_symbol: null,
  strike: null,
  expiry: null,
  option_type: null,
  action: 'Sold Short',
  description: 'CALL AAPL 03/15/26 200.00',
  quantity: '1',
  price: '5.00',
  commission: '0.65',
  amount: '500.00',
  category: 'OPTIONS_SELL_TO_OPEN',
  status: 'ACTIVE',
  deleted_at: null,
};

const mockPaginatedResponse: PaginatedResponse<Transaction> = {
  items: [mockTransaction],
  total: 1,
  offset: 0,
  limit: 100,
};

describe('TransactionService', () => {
  let service: TransactionService;
  let controller: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: '/api/v1' },
        TransactionService,
      ],
    });
    service = TestBed.inject(TransactionService);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    controller.verify();
  });

  describe('getTransactions()', () => {
    it('should GET /api/v1/transactions without params and return paginated response', (done) => {
      service.getTransactions().subscribe({
        next: (res) => {
          expect(res).toEqual(mockPaginatedResponse);
          done();
        },
        error: done.fail,
      });

      const req = controller.expectOne('/api/v1/transactions');
      expect(req.request.method).toBe('GET');
      req.flush(mockPaginatedResponse);
    });

    it('should serialize offset and limit query params', (done) => {
      const params: TransactionQueryParams = { offset: 10, limit: 50 };

      service.getTransactions(params).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/transactions');
      expect(req.request.params.get('offset')).toBe('10');
      expect(req.request.params.get('limit')).toBe('50');
      req.flush(mockPaginatedResponse);
    });

    it('should serialize symbol query param', (done) => {
      service.getTransactions({ symbol: 'AAPL' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/transactions');
      expect(req.request.params.get('symbol')).toBe('AAPL');
      req.flush(mockPaginatedResponse);
    });

    it('should serialize a single category as a repeated query param', (done) => {
      service.getTransactions({ category: ['OPTIONS_SELL_TO_OPEN'] }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/transactions');
      expect(req.request.params.getAll('category')).toEqual(['OPTIONS_SELL_TO_OPEN']);
      req.flush(mockPaginatedResponse);
    });

    it('should serialize multiple categories as repeated query params', (done) => {
      service
        .getTransactions({ category: ['OPTIONS_SELL_TO_OPEN', 'OPTIONS_BUY_TO_OPEN'] })
        .subscribe({ next: () => done(), error: done.fail });

      const req = controller.expectOne((r) => r.url === '/api/v1/transactions');
      expect(req.request.params.getAll('category')).toEqual([
        'OPTIONS_SELL_TO_OPEN',
        'OPTIONS_BUY_TO_OPEN',
      ]);
      req.flush(mockPaginatedResponse);
    });

    it('should omit category param when array is empty', (done) => {
      service.getTransactions({ category: [] }).subscribe({ next: () => done(), error: done.fail });

      const req = controller.expectOne((r) => r.url === '/api/v1/transactions');
      expect(req.request.params.has('category')).toBe(false);
      req.flush(mockPaginatedResponse);
    });

    it('should serialize status as repeated query params', (done) => {
      service
        .getTransactions({ status: ['DUPLICATE', 'PARSE_ERROR'] })
        .subscribe({ next: () => done(), error: done.fail });

      const req = controller.expectOne((r) => r.url === '/api/v1/transactions');
      expect(req.request.params.getAll('status')).toEqual(['DUPLICATE', 'PARSE_ERROR']);
      req.flush(mockPaginatedResponse);
    });

    it('should omit status param when array is empty', (done) => {
      service.getTransactions({ status: [] }).subscribe({ next: () => done(), error: done.fail });

      const req = controller.expectOne((r) => r.url === '/api/v1/transactions');
      expect(req.request.params.has('status')).toBe(false);
      req.flush(mockPaginatedResponse);
    });

    it('should serialize start_date and end_date query params', (done) => {
      service.getTransactions({ start_date: '2026-01-01', end_date: '2026-03-31' }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/transactions');
      expect(req.request.params.get('start_date')).toBe('2026-01-01');
      expect(req.request.params.get('end_date')).toBe('2026-03-31');
      req.flush(mockPaginatedResponse);
    });

    it('should omit undefined params', (done) => {
      service.getTransactions({ symbol: undefined, limit: 20 }).subscribe({
        next: () => done(),
        error: done.fail,
      });

      const req = controller.expectOne((r) => r.url === '/api/v1/transactions');
      expect(req.request.params.has('symbol')).toBe(false);
      expect(req.request.params.get('limit')).toBe('20');
      req.flush(mockPaginatedResponse);
    });
  });
});
