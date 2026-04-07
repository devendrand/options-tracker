import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Subject, of, throwError } from 'rxjs';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { PositionsComponent, POSITION_STATUSES } from './positions.component';
import { PositionService } from '@core/services/position.service';
import { OptionsPosition, PositionListResponse } from '@core/models/position.model';
import { PositionDrawerComponent } from './position-drawer/position-drawer.component';

@Component({
  selector: 'app-position-drawer',
  template: '<div data-testid="mock-drawer"></div>',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
class MockPositionDrawerComponent {
  readonly positionId = input.required<string>();
}

function makePosition(overrides: Partial<OptionsPosition> = {}): OptionsPosition {
  return {
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
    opened_at: '2026-01-05',
    closed_at: '2026-02-10',
    ...overrides,
  };
}

function makeListResponse(
  options_items: OptionsPosition[] = [makePosition()],
  total = 1,
): PositionListResponse {
  return { options_items, equity_items: [], total, offset: 0, limit: 100 };
}

function mockEvent(value: string): Event {
  return { target: { value } } as unknown as Event;
}

describe('PositionsComponent', () => {
  let positionServiceMock: jest.Mocked<Pick<PositionService, 'getPositions'>>;

  beforeEach(async () => {
    positionServiceMock = {
      getPositions: jest.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [PositionsComponent],
      providers: [{ provide: PositionService, useValue: positionServiceMock }],
    })
      .overrideComponent(PositionsComponent, {
        remove: { imports: [PositionDrawerComponent] },
        add: { imports: [MockPositionDrawerComponent] },
      })
      .compileComponents();
  });

  // ── 1. Initial state ──────────────────────────────────────────────────────

  describe('initial state', () => {
    it('1. should create without error', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance).toBeTruthy();
    });

    it('2. should call getPositions on ngOnInit with { offset: 0, limit: 100 }', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(positionServiceMock.getPositions).toHaveBeenCalledWith({ offset: 0, limit: 100 });
    });

    it('3. should show loading state while request is in-flight', () => {
      const subject = new Subject<PositionListResponse>();
      positionServiceMock.getPositions.mockReturnValue(subject.asObservable());
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="loading-state"]'));
      expect(loading).not.toBeNull();
      subject.complete();
    });
  });

  // ── 2. Successful data load ───────────────────────────────────────────────

  describe('successful data load', () => {
    it('4. should render the positions table on success', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const table = fixture.debugElement.query(By.css('[data-testid="positions-table"]'));
      expect(table).not.toBeNull();
    });

    it('5. should render the correct number of rows from options_items', () => {
      const items = [
        makePosition({ id: 'pos-1' }),
        makePosition({ id: 'pos-2' }),
        makePosition({ id: 'pos-3' }),
      ];
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse(items, 3)));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const rows = fixture.debugElement.queryAll(By.css('[data-testid^="position-row-"]'));
      expect(rows.length).toBe(3);
    });

    it('6. should display underlying, option_symbol, and direction in the first row', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="position-row-pos-1"]'));
      const text = row.nativeElement.textContent;
      expect(text).toContain('AAPL');
      expect(text).toContain('AAPL240119C00200000');
      expect(text).toContain('SHORT');
    });

    it('7. should show empty state when options_items is empty', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse([], 0)));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const emptyState = fixture.debugElement.query(By.css('[data-testid="empty-state"]'));
      expect(emptyState).not.toBeNull();
      const table = fixture.debugElement.query(By.css('[data-testid="positions-table"]'));
      expect(table).toBeNull();
    });

    it('8. should show covered-call badge when is_covered_call is true', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(makeListResponse([makePosition({ id: 'pos-1', is_covered_call: true })], 1)),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const badge = fixture.debugElement.query(By.css('[data-testid="covered-call-badge"]'));
      expect(badge).not.toBeNull();
    });

    it('9. should not show covered-call badge when is_covered_call is false', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(makeListResponse([makePosition({ id: 'pos-1', is_covered_call: false })], 1)),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const badge = fixture.debugElement.query(By.css('[data-testid="covered-call-badge"]'));
      expect(badge).toBeNull();
    });

    it('10. should show PARTIALLY_CLOSED badge for a partially-closed position', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(makeListResponse([makePosition({ id: 'pos-1', status: 'PARTIALLY_CLOSED' })], 1)),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const badge = fixture.debugElement.query(By.css('[data-testid="partial-badge"]'));
      expect(badge).not.toBeNull();
    });

    it('11. should not show PARTIALLY_CLOSED badge for non-partial positions', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(makeListResponse([makePosition({ id: 'pos-1', status: 'CLOSED' })], 1)),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const badge = fixture.debugElement.query(By.css('[data-testid="partial-badge"]'));
      expect(badge).toBeNull();
    });

    it('12. should apply positive class to P&L cell when realized_pnl is positive', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(makeListResponse([makePosition({ id: 'pos-1', realized_pnl: '350.00' })], 1)),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const pnlCell = fixture.debugElement.query(By.css('[data-testid="pnl-cell"]'));
      expect(pnlCell.nativeElement.className).toContain('positive');
    });

    it('13. should apply negative class to P&L cell when realized_pnl is negative', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(makeListResponse([makePosition({ id: 'pos-1', realized_pnl: '-100.00' })], 1)),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const pnlCell = fixture.debugElement.query(By.css('[data-testid="pnl-cell"]'));
      expect(pnlCell.nativeElement.className).toContain('negative');
    });

    it('14. should show "—" when realized_pnl is null', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(makeListResponse([makePosition({ id: 'pos-1', realized_pnl: null })], 1)),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const pnlCell = fixture.debugElement.query(By.css('[data-testid="pnl-cell"]'));
      expect(pnlCell.nativeElement.textContent.trim()).toBe('—');
    });
  });

  // ── 3. Expand / collapse drawers ──────────────────────────────────────────

  describe('expand / collapse drawers', () => {
    it('15. should have an expand button for each row', () => {
      const items = [makePosition({ id: 'pos-1' }), makePosition({ id: 'pos-2' })];
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse(items, 2)));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const expandBtns = fixture.debugElement.queryAll(By.css('[data-testid^="expand-btn-"]'));
      expect(expandBtns.length).toBe(2);
    });

    it('16. clicking expand renders the drawer row for that position', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();

      fixture.debugElement.query(By.css('[data-testid="expand-btn-pos-1"]')).nativeElement.click();
      fixture.detectChanges();

      const drawer = fixture.debugElement.query(By.css('[data-testid="drawer-row-pos-1"]'));
      expect(drawer).not.toBeNull();
    });

    it('17. clicking the same expand button again collapses the drawer', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();

      const btn = fixture.debugElement.query(
        By.css('[data-testid="expand-btn-pos-1"]'),
      ).nativeElement;
      btn.click();
      fixture.detectChanges();
      btn.click();
      fixture.detectChanges();

      const drawer = fixture.debugElement.query(By.css('[data-testid="drawer-row-pos-1"]'));
      expect(drawer).toBeNull();
    });

    it('18. two drawers can be open simultaneously', () => {
      const items = [makePosition({ id: 'pos-1' }), makePosition({ id: 'pos-2' })];
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse(items, 2)));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();

      fixture.debugElement.query(By.css('[data-testid="expand-btn-pos-1"]')).nativeElement.click();
      fixture.debugElement.query(By.css('[data-testid="expand-btn-pos-2"]')).nativeElement.click();
      fixture.detectChanges();

      expect(fixture.debugElement.query(By.css('[data-testid="drawer-row-pos-1"]'))).not.toBeNull();
      expect(fixture.debugElement.query(By.css('[data-testid="drawer-row-pos-2"]'))).not.toBeNull();
    });

    it('19. collapsing P1 drawer does not affect P2 drawer', () => {
      const items = [makePosition({ id: 'pos-1' }), makePosition({ id: 'pos-2' })];
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse(items, 2)));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();

      fixture.debugElement.query(By.css('[data-testid="expand-btn-pos-1"]')).nativeElement.click();
      fixture.debugElement.query(By.css('[data-testid="expand-btn-pos-2"]')).nativeElement.click();
      fixture.detectChanges();

      // Collapse P1
      fixture.debugElement.query(By.css('[data-testid="expand-btn-pos-1"]')).nativeElement.click();
      fixture.detectChanges();

      expect(fixture.debugElement.query(By.css('[data-testid="drawer-row-pos-1"]'))).toBeNull();
      expect(fixture.debugElement.query(By.css('[data-testid="drawer-row-pos-2"]'))).not.toBeNull();
    });

    it('20. toggleDrawer creates a new Set reference on each call (immutable update)', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const component = fixture.componentInstance;

      const initial = component.expandedIds();
      component.toggleDrawer('pos-1');
      const afterExpand = component.expandedIds();
      component.toggleDrawer('pos-1');
      const afterCollapse = component.expandedIds();

      expect(afterExpand).not.toBe(initial);
      expect(afterCollapse).not.toBe(afterExpand);
    });
  });

  // ── 4. Filters ────────────────────────────────────────────────────────────

  describe('filters', () => {
    it('21. status dropdown has "All Statuses" + all 6 status options', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const options = fixture.debugElement.queryAll(By.css('[data-testid="status-filter"] option'));
      expect(options.length).toBe(POSITION_STATUSES.length + 1); // +1 for "All Statuses"
    });

    it('22. selecting OPEN calls getPositions with { status: OPEN, offset: 0 }', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      positionServiceMock.getPositions.mockClear();
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));

      fixture.componentInstance.onStatusChange(mockEvent('OPEN'));
      expect(positionServiceMock.getPositions).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'OPEN', offset: 0 }),
      );
    });

    it('23. omits status param when status is empty string', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      positionServiceMock.getPositions.mockClear();
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));

      fixture.componentInstance.onStatusChange(mockEvent(''));
      const call = positionServiceMock.getPositions.mock.calls[0][0];
      expect(call).not.toHaveProperty('status');
    });

    it('24. typing underlying includes the underlying param', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      positionServiceMock.getPositions.mockClear();
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));

      fixture.componentInstance.onUnderlyingChange(mockEvent('AAPL'));
      expect(positionServiceMock.getPositions).toHaveBeenCalledWith(
        expect.objectContaining({ underlying: 'AAPL' }),
      );
    });

    it('25. omits underlying param when underlying is empty', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      positionServiceMock.getPositions.mockClear();
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));

      fixture.componentInstance.onUnderlyingChange(mockEvent(''));
      const call = positionServiceMock.getPositions.mock.calls[0][0];
      expect(call).not.toHaveProperty('underlying');
    });

    it('26. reset clears all filters and reloads with default params', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();

      fixture.componentInstance.onStatusChange(mockEvent('OPEN'));
      fixture.componentInstance.onUnderlyingChange(mockEvent('AAPL'));

      positionServiceMock.getPositions.mockClear();
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));

      fixture.componentInstance.resetFilters();
      expect(positionServiceMock.getPositions).toHaveBeenCalledWith({ offset: 0, limit: 100 });
      expect(fixture.componentInstance.selectedStatus()).toBe('');
      expect(fixture.componentInstance.underlying()).toBe('');
    });
  });

  // ── 5. Pagination ─────────────────────────────────────────────────────────

  describe('pagination', () => {
    function setupWithPagination() {
      const items = Array.from({ length: 100 }, (_, i) => makePosition({ id: `pos-${i}` }));
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse(items, 250)));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      return fixture;
    }

    it('27. should show pagination controls when total > limit', () => {
      const fixture = setupWithPagination();
      const pagination = fixture.debugElement.query(By.css('[data-testid="pagination-controls"]'));
      expect(pagination).not.toBeNull();
    });

    it('28. should hide pagination controls when total <= limit', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse([makePosition()], 1)));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const pagination = fixture.debugElement.query(By.css('[data-testid="pagination-controls"]'));
      expect(pagination).toBeNull();
    });

    it('29. should disable Previous button on the first page', () => {
      const fixture = setupWithPagination();
      const prevBtn: HTMLButtonElement = fixture.debugElement.query(
        By.css('[data-testid="prev-btn"]'),
      ).nativeElement;
      expect(prevBtn.disabled).toBe(true);
    });

    it('30. should disable Next button on the last page', () => {
      const items = Array.from({ length: 50 }, (_, i) => makePosition({ id: `pos-${i}` }));
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse(items, 150)));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.componentInstance.offset.set(100);
      fixture.detectChanges();
      const nextBtn: HTMLButtonElement = fixture.debugElement.query(
        By.css('[data-testid="next-btn"]'),
      ).nativeElement;
      expect(nextBtn.disabled).toBe(true);
    });

    it('31. should advance offset by limit and reload when Next is clicked', () => {
      const fixture = setupWithPagination();
      positionServiceMock.getPositions.mockClear();
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));

      fixture.componentInstance.nextPage();
      expect(positionServiceMock.getPositions).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 100, limit: 100 }),
      );
    });

    it('32. should decrement offset by limit and reload when Previous is clicked', () => {
      const items = Array.from({ length: 100 }, (_, i) => makePosition({ id: `pos-${i}` }));
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse(items, 250)));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();

      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse(items, 250)));
      fixture.componentInstance.nextPage();

      positionServiceMock.getPositions.mockClear();
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse(items, 250)));

      fixture.componentInstance.prevPage();
      expect(positionServiceMock.getPositions).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 0, limit: 100 }),
      );
    });

    it('33. should reset offset and use new limit when page size is changed', () => {
      const fixture = setupWithPagination();
      positionServiceMock.getPositions.mockClear();
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));

      fixture.componentInstance.onLimitChange(mockEvent('50'));
      expect(positionServiceMock.getPositions).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 0, limit: 50 }),
      );
    });
  });

  // ── 6. Error handling ─────────────────────────────────────────────────────

  describe('error handling', () => {
    it('34. should show error state when API call fails', () => {
      positionServiceMock.getPositions.mockReturnValue(
        throwError(() => ({ message: 'API error' })),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const errorState = fixture.debugElement.query(By.css('[data-testid="error-state"]'));
      expect(errorState).not.toBeNull();
    });

    it('35. should display the error message text', () => {
      positionServiceMock.getPositions.mockReturnValue(
        throwError(() => ({ message: 'Failed to fetch' })),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const errorState = fixture.debugElement.query(By.css('[data-testid="error-state"]'));
      expect(errorState.nativeElement.textContent).toContain('Failed to fetch');
    });

    it('36. should call getPositions again when Retry is clicked', () => {
      positionServiceMock.getPositions.mockReturnValue(throwError(() => ({ message: 'error' })));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();

      positionServiceMock.getPositions.mockClear();
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));

      const retryBtn = fixture.debugElement.query(By.css('[data-testid="retry-btn"]'));
      retryBtn.nativeElement.click();
      expect(positionServiceMock.getPositions).toHaveBeenCalledTimes(1);
    });

    it('37. should use fallback message when error has no message property', () => {
      positionServiceMock.getPositions.mockReturnValue(throwError(() => ({})));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const errorState = fixture.debugElement.query(By.css('[data-testid="error-state"]'));
      expect(errorState.nativeElement.textContent).toContain('Failed to load positions.');
    });
  });

  // ── 7. pnlClass helper ────────────────────────────────────────────────────

  describe('pnlClass()', () => {
    it('38. should return "" for null P&L', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.pnlClass(null)).toBe('');
    });

    it('39. should return "positive" for non-negative P&L', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.pnlClass('350.00')).toBe('positive');
    });

    it('40. should return "negative" for negative P&L', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.pnlClass('-100.00')).toBe('negative');
    });
  });

  // ── 8. daysHeld / daysToExpiry / isClosed helpers ────────────────────────────

  describe('daysHeld()', () => {
    it('41. returns correct number of days for a closed position', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(
        fixture.componentInstance.daysHeld({ opened_at: '2026-01-05', closed_at: '2026-02-10' }),
      ).toBe(36);
    });

    it('42. returns null when opened_at is null', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(
        fixture.componentInstance.daysHeld({ opened_at: null, closed_at: '2026-02-10' }),
      ).toBeNull();
    });

    it('43. returns null when closed_at is null', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(
        fixture.componentInstance.daysHeld({ opened_at: '2026-01-05', closed_at: null }),
      ).toBeNull();
    });
  });

  describe('daysToExpiry()', () => {
    it('44. returns a positive number for a far-future expiry', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const result = fixture.componentInstance.daysToExpiry('2099-12-31');
      expect(result).not.toBeNull();
      expect(result!).toBeGreaterThan(0);
    });

    it('45. returns null for empty expiry string', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.daysToExpiry('')).toBeNull();
    });
  });

  describe('isClosed()', () => {
    it('46. returns true for CLOSED', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('CLOSED')).toBe(true);
    });

    it('47. returns true for EXPIRED', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('EXPIRED')).toBe(true);
    });

    it('48. returns true for ASSIGNED', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('ASSIGNED')).toBe(true);
    });

    it('49. returns true for EXERCISED', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('EXERCISED')).toBe(true);
    });

    it('50. returns false for OPEN', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('OPEN')).toBe(false);
    });

    it('51. returns false for PARTIALLY_CLOSED', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('PARTIALLY_CLOSED')).toBe(false);
    });
  });

  // ── 9. Date/DTE/Held columns in the positions table ──────────────────────────

  describe('positions table date columns', () => {
    it('52. table shows Opened, Closed/DTE, and Held column headers', () => {
      positionServiceMock.getPositions.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const headers = fixture.debugElement
        .query(By.css('[data-testid="positions-table"]'))
        .queryAll(By.css('th'));
      const texts = headers.map((h) => h.nativeElement.textContent.trim());
      expect(texts).toContain('Opened');
      expect(texts).toContain('Closed / DTE');
      expect(texts).toContain('Held');
    });

    it('53. closed position row shows opened_at date formatted', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(
          makeListResponse([
            makePosition({ id: 'pos-1', status: 'CLOSED', opened_at: '2026-01-05' }),
          ]),
        ),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="position-row-pos-1"]'));
      expect(row.nativeElement.textContent).toContain('Jan 5, 2026');
    });

    it('54. closed position row shows closed_at date in Closed/DTE column', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(
          makeListResponse([
            makePosition({ id: 'pos-1', status: 'CLOSED', closed_at: '2026-02-10' }),
          ]),
        ),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="position-row-pos-1"]'));
      expect(row.nativeElement.textContent).toContain('Feb 10, 2026');
    });

    it('55. closed position shows days held', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(
          makeListResponse([
            makePosition({
              id: 'pos-1',
              status: 'CLOSED',
              opened_at: '2026-01-05',
              closed_at: '2026-02-10',
            }),
          ]),
        ),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="position-row-pos-1"]'));
      expect(row.nativeElement.textContent).toContain('36d');
    });

    it('56. open position shows days to expiry in Closed/DTE column', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(
          makeListResponse([
            makePosition({
              id: 'pos-1',
              status: 'OPEN',
              opened_at: '2026-01-05',
              closed_at: null,
              expiry: '2099-12-31',
            }),
          ]),
        ),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="position-row-pos-1"]'));
      expect(row.nativeElement.textContent).toMatch(/\d+d/);
    });

    it('57. open position shows em dash in Held column', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(
          makeListResponse([
            makePosition({
              id: 'pos-1',
              status: 'OPEN',
              opened_at: '2026-01-05',
              closed_at: null,
              expiry: '2099-12-31',
            }),
          ]),
        ),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="position-row-pos-1"]'));
      expect(row.nativeElement.textContent).toContain('—');
    });

    it('58. null opened_at displays empty Opened cell', () => {
      positionServiceMock.getPositions.mockReturnValue(
        of(
          makeListResponse([
            makePosition({ id: 'pos-1', status: 'OPEN', opened_at: null, closed_at: null }),
          ]),
        ),
      );
      const fixture = TestBed.createComponent(PositionsComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="position-row-pos-1"]'));
      // daysHeld is null → Held shows —
      expect(row.nativeElement.textContent).toContain('—');
    });
  });
});
