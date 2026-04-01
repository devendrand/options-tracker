import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Subject, of, throwError } from 'rxjs';
import { DatePipe } from '@angular/common';
import { provideRouter } from '@angular/router';
import { TransactionsComponent, DEDUP_STATUSES } from './transactions.component';
import { TransactionService } from '@core/services/transaction.service';
import { Transaction, TransactionCategory } from '@core/models/transaction.model';
import { PaginatedResponse } from '@core/models/pagination.model';

function makeTx(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: 'tx-1',
    upload_id: 'abcd1234-5678-90ef-ghij-klmnopqrstuv',
    broker_name: 'etrade',
    trade_date: '2026-03-15',
    transaction_date: '2026-03-15',
    settlement_date: '2026-03-17',
    symbol: 'AAPL',
    option_symbol: null,
    strike: null,
    expiry: null,
    option_type: null,
    action: 'Sold Short',
    description: 'CALL AAPL 03/20/26 200.00',
    quantity: '1',
    price: '2.50',
    commission: '0.65',
    amount: '250.00',
    category: 'OPTIONS_SELL_TO_OPEN',
    status: 'ACTIVE',
    deleted_at: null,
    ...overrides,
  };
}

function makeResponse(
  items: Transaction[] = [makeTx()],
  total = 1,
): PaginatedResponse<Transaction> {
  return { items, total, offset: 0, limit: 100 };
}

function mockEvent(value: string): Event {
  return { target: { value } } as unknown as Event;
}

function mockMultiSelectEvent(values: string[]): Event {
  return {
    target: {
      selectedOptions: values.map((v) => ({ value: v })),
    },
  } as unknown as Event;
}

describe('TransactionsComponent', () => {
  let transactionServiceMock: jest.Mocked<Pick<TransactionService, 'getTransactions'>>;

  beforeEach(async () => {
    transactionServiceMock = {
      getTransactions: jest.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [TransactionsComponent],
      providers: [
        { provide: TransactionService, useValue: transactionServiceMock },
        DatePipe,
        provideRouter([]),
      ],
    }).compileComponents();
  });

  // ── 1. Initial state ──────────────────────────────────────────────────────────

  describe('initial state', () => {
    it('1. should create without error', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance).toBeTruthy();
    });

    it('2. should call getTransactions on ngOnInit with default params (offset: 0, limit: 100)', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith({
        offset: 0,
        limit: 100,
      });
    });

    it('3. should show loading state while request is in-flight', () => {
      const subject = new Subject<PaginatedResponse<Transaction>>();
      transactionServiceMock.getTransactions.mockReturnValue(subject.asObservable());
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="loading-state"]'));
      expect(loading).not.toBeNull();
      subject.complete();
    });

    it('4. should not render the table during loading', () => {
      const subject = new Subject<PaginatedResponse<Transaction>>();
      transactionServiceMock.getTransactions.mockReturnValue(subject.asObservable());
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const table = fixture.debugElement.query(By.css('[data-testid="transactions-table"]'));
      expect(table).toBeNull();
      subject.complete();
    });
  });

  // ── 2. Successful data load ───────────────────────────────────────────────────

  describe('successful data load', () => {
    it('5. should render the transactions table after a successful response', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const table = fixture.debugElement.query(By.css('[data-testid="transactions-table"]'));
      expect(table).not.toBeNull();
    });

    it('6. should render the correct number of rows', () => {
      const items = [makeTx({ id: 'tx-1' }), makeTx({ id: 'tx-2' }), makeTx({ id: 'tx-3' })];
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse(items, 3)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const rows = fixture.debugElement.queryAll(By.css('[data-testid="transaction-row"]'));
      expect(rows.length).toBe(3);
    });

    it('7. should display trade_date, symbol, category label, amount, and status in the first row', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="transaction-row"]'));
      const text = row.nativeElement.textContent;
      expect(text).toContain('Mar 15, 2026');
      expect(text).toContain('AAPL');
      expect(text).toContain('Sell to Open');
      expect(text).toContain('250.00');
      expect(text).toContain('ACTIVE');
    });

    it('8. should show empty state when items is [] and total is 0', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse([], 0)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const emptyState = fixture.debugElement.query(By.css('[data-testid="empty-state"]'));
      expect(emptyState).not.toBeNull();
      const table = fixture.debugElement.query(By.css('[data-testid="transactions-table"]'));
      expect(table).toBeNull();
    });

    it('9. should render pagination controls when total > limit', () => {
      const items = Array.from({ length: 100 }, (_, i) => makeTx({ id: `tx-${i}` }));
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse(items, 150)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const pagination = fixture.debugElement.query(By.css('[data-testid="pagination-controls"]'));
      expect(pagination).not.toBeNull();
    });

    it('10. should hide pagination controls when total <= limit', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse([makeTx()], 1)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const pagination = fixture.debugElement.query(By.css('[data-testid="pagination-controls"]'));
      expect(pagination).toBeNull();
    });

    it('11. should display correct "Page X of Y" text', () => {
      const items = Array.from({ length: 100 }, (_, i) => makeTx({ id: `tx-${i}` }));
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse(items, 250)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const pageInfo = fixture.debugElement.query(By.css('[data-testid="page-info"]'));
      expect(pageInfo.nativeElement.textContent.trim()).toBe('Page 1 of 3');
    });
  });

  // ── 3. Filter controls ────────────────────────────────────────────────────────

  describe('filter controls', () => {
    it('12. should render all 15 category options in the multi-select dropdown', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const options = fixture.debugElement.queryAll(
        By.css('[data-testid="category-filter"] option'),
      );
      expect(options.length).toBe(15);
    });

    it('13. should call getTransactions with category array when categories are selected', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.onCategoryMultiChange(
        mockMultiSelectEvent(['OPTIONS_SELL_TO_OPEN', 'OPTIONS_BUY_TO_OPEN']),
      );
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({
          category: ['OPTIONS_SELL_TO_OPEN', 'OPTIONS_BUY_TO_OPEN'] as TransactionCategory[],
        }),
      );
    });

    it('13b. should omit category param when selection is cleared (empty array)', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.onCategoryMultiChange(mockMultiSelectEvent([]));
      const call = transactionServiceMock.getTransactions.mock.calls[0][0];
      expect(call).not.toHaveProperty('category');
    });

    it('14. should call getTransactions with symbol param when symbol input changes', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.onSymbolChange(mockEvent('AAPL'));
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ symbol: 'AAPL' }),
      );
    });

    it('15. should include start_date param when start date is set', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.onStartDateChange(mockEvent('2026-01-01'));
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ start_date: '2026-01-01' }),
      );
    });

    it('16. should include end_date param when end date is set', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.onEndDateChange(mockEvent('2026-03-31'));
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ end_date: '2026-03-31' }),
      );
    });

    it('17. should reset offset to 0 when any filter changes', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();

      fixture.componentInstance.offset.set(100);
      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.onCategoryMultiChange(
        mockMultiSelectEvent(['OPTIONS_SELL_TO_OPEN']),
      );
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 0 }),
      );
    });

    it('18. should clear all filters and reload with default params when reset is clicked', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();

      fixture.componentInstance.onCategoryMultiChange(
        mockMultiSelectEvent(['OPTIONS_SELL_TO_OPEN']),
      );
      fixture.componentInstance.onStatusMultiChange(mockMultiSelectEvent(['DUPLICATE']));
      fixture.componentInstance.onSymbolChange(mockEvent('AAPL'));

      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.resetFilters();
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith({
        offset: 0,
        limit: 100,
      });
      expect(fixture.componentInstance.selectedCategories()).toEqual([]);
      expect(fixture.componentInstance.selectedStatuses()).toEqual([]);
    });
  });

  // ── 4. Pagination ─────────────────────────────────────────────────────────────

  describe('pagination', () => {
    function setupWithPagination() {
      const items = Array.from({ length: 100 }, (_, i) => makeTx({ id: `tx-${i}` }));
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse(items, 250)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      return fixture;
    }

    it('19. should disable "Previous" button on the first page', () => {
      const fixture = setupWithPagination();
      const prevBtn: HTMLButtonElement = fixture.debugElement.query(
        By.css('[data-testid="prev-btn"]'),
      ).nativeElement;
      expect(prevBtn.disabled).toBe(true);
    });

    it('20. should disable "Next" button on the last page', () => {
      // total=150, limit=100, offset=100 → page 2 of 2 (last page), total > limit so pagination renders
      const items = Array.from({ length: 50 }, (_, i) => makeTx({ id: `tx-${i}` }));
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse(items, 150)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.componentInstance.offset.set(100);
      fixture.detectChanges();
      const nextBtn: HTMLButtonElement = fixture.debugElement.query(
        By.css('[data-testid="next-btn"]'),
      ).nativeElement;
      expect(nextBtn.disabled).toBe(true);
    });

    it('21. should increment offset by limit and call getTransactions when "Next" is clicked', () => {
      const fixture = setupWithPagination();
      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.nextPage();
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 100, limit: 100 }),
      );
    });

    it('22. should decrement offset by limit and call getTransactions when "Previous" is clicked', () => {
      const items = Array.from({ length: 100 }, (_, i) => makeTx({ id: `tx-${i}` }));
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse(items, 250)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();

      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse(items, 250)));
      fixture.componentInstance.nextPage();

      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse(items, 250)));

      fixture.componentInstance.prevPage();
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 0, limit: 100 }),
      );
    });

    it('23. should reset offset to 0 and use new limit when page size is changed', () => {
      const fixture = setupWithPagination();
      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.onLimitChange(mockEvent('50'));
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 0, limit: 50 }),
      );
    });
  });

  // ── 5. Error handling ─────────────────────────────────────────────────────────

  describe('error handling', () => {
    it('24. should show the error state when the API call fails', () => {
      transactionServiceMock.getTransactions.mockReturnValue(
        throwError(() => ({ message: 'API error' })),
      );
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const errorState = fixture.debugElement.query(By.css('[data-testid="error-state"]'));
      expect(errorState).not.toBeNull();
    });

    it('25. should display the error message text', () => {
      transactionServiceMock.getTransactions.mockReturnValue(
        throwError(() => ({ message: 'Failed to load data' })),
      );
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const errorState = fixture.debugElement.query(By.css('[data-testid="error-state"]'));
      expect(errorState.nativeElement.textContent).toContain('Failed to load data');
    });

    it('26. should call getTransactions again when "Retry" is clicked', () => {
      transactionServiceMock.getTransactions.mockReturnValue(
        throwError(() => ({ message: 'error' })),
      );
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();

      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      const retryBtn = fixture.debugElement.query(By.css('[data-testid="retry-btn"]'));
      retryBtn.nativeElement.click();
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledTimes(1);
    });

    it('27. should clear loading state after an error', () => {
      transactionServiceMock.getTransactions.mockReturnValue(
        throwError(() => ({ message: 'error' })),
      );
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const loadingState = fixture.debugElement.query(By.css('[data-testid="loading-state"]'));
      expect(loadingState).toBeNull();
    });

    it('28b. should use fallback message when error has no message property', () => {
      transactionServiceMock.getTransactions.mockReturnValue(throwError(() => ({})));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const errorState = fixture.debugElement.query(By.css('[data-testid="error-state"]'));
      expect(errorState.nativeElement.textContent).toContain('Failed to load transactions.');
    });
  });

  // ── 6. Symbol null display ────────────────────────────────────────────────────

  describe('null symbol display', () => {
    it('28. should render "—" when transaction symbol is null', () => {
      const tx = makeTx({ symbol: null });
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse([tx], 1)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="transaction-row"]'));
      expect(row.nativeElement.textContent).toContain('—');
    });
  });

  // ── 7. Status multi-select filter ────────────────────────────────────────────

  describe('status filter', () => {
    it('29. should render all 4 dedup status options in the status filter', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const options = fixture.debugElement.queryAll(By.css('[data-testid="status-filter"] option'));
      expect(options.length).toBe(4);
      const values = options.map((o) => o.nativeElement.value);
      expect(values).toEqual(DEDUP_STATUSES);
    });

    it('30. should call getTransactions with status array when statuses are selected', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.onStatusMultiChange(
        mockMultiSelectEvent(['DUPLICATE', 'PARSE_ERROR']),
      );
      expect(transactionServiceMock.getTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ status: ['DUPLICATE', 'PARSE_ERROR'] }),
      );
    });

    it('31. should omit status param when status selection is cleared', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      transactionServiceMock.getTransactions.mockClear();
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));

      fixture.componentInstance.onStatusMultiChange(mockMultiSelectEvent([]));
      const call = transactionServiceMock.getTransactions.mock.calls[0][0];
      expect(call).not.toHaveProperty('status');
    });

    it('32. should reset selectedStatuses to [] when resetFilters is called', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();

      fixture.componentInstance.onStatusMultiChange(mockMultiSelectEvent(['DUPLICATE']));
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      fixture.componentInstance.resetFilters();

      expect(fixture.componentInstance.selectedStatuses()).toEqual([]);
    });
  });

  // ── 8. Upload column ──────────────────────────────────────────────────────────

  describe('upload column', () => {
    it('33. should render an "Upload" column header in the table', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const headers = fixture.debugElement.queryAll(By.css('th'));
      const headerTexts = headers.map((h) => h.nativeElement.textContent.trim());
      expect(headerTexts).toContain('Upload');
    });

    it('34. should render an upload link in each row pointing to /uploads/{upload_id}', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const link = fixture.debugElement.query(By.css('[data-testid="upload-link"]'));
      expect(link).not.toBeNull();
      expect(
        link.attributes['ng-reflect-router-link'] ?? link.nativeElement.getAttribute('href'),
      ).toContain('abcd1234-5678-90ef-ghij-klmnopqrstuv');
    });

    it('35. should display the first 8 characters of upload_id in the link text', () => {
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse()));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const link = fixture.debugElement.query(By.css('[data-testid="upload-link"]'));
      expect(link.nativeElement.textContent.trim()).toBe('abcd1234');
    });
  });

  // ── 9. Row visual distinction ─────────────────────────────────────────────────

  describe('row visual distinction', () => {
    it('36. should apply "row-duplicate" class to a DUPLICATE row', () => {
      const tx = makeTx({ status: 'DUPLICATE' });
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse([tx], 1)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="transaction-row"]'));
      expect(row.nativeElement.classList).toContain('row-duplicate');
    });

    it('37. should apply "row-possible-duplicate" class to a POSSIBLE_DUPLICATE row', () => {
      const tx = makeTx({ status: 'POSSIBLE_DUPLICATE' });
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse([tx], 1)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="transaction-row"]'));
      expect(row.nativeElement.classList).toContain('row-possible-duplicate');
    });

    it('38. should apply "row-parse-error" class to a PARSE_ERROR row', () => {
      const tx = makeTx({ status: 'PARSE_ERROR' });
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse([tx], 1)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="transaction-row"]'));
      expect(row.nativeElement.classList).toContain('row-parse-error');
    });

    it('39. should not apply any special class to a UNIQUE row', () => {
      const tx = makeTx({ status: 'UNIQUE' });
      transactionServiceMock.getTransactions.mockReturnValue(of(makeResponse([tx], 1)));
      const fixture = TestBed.createComponent(TransactionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="transaction-row"]'));
      expect(row.nativeElement.className.trim()).toBe('');
    });
  });
});
