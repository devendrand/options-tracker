import { Component, Input } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Subject, of, throwError } from 'rxjs';
import { PnlSummaryComponent } from './pnl-summary.component';
import { PnlService } from '@core/services/pnl.service';
import { PnlGroupBy, PnlSummary } from '@core/models/pnl.model';
import { PositionDrawerComponent } from '@features/positions/position-drawer/position-drawer.component';
import { PositionListResponse } from '@core/models/position.model';

@Component({ selector: 'app-position-drawer', template: '', standalone: true })
class MockPositionDrawerComponent {
  @Input() positionId!: string;
}

function makeBucketResponse(
  optionsItems: PositionListResponse['options_items'] = [],
  equityItems: PositionListResponse['equity_items'] = [],
): PositionListResponse {
  return {
    total: optionsItems.length + equityItems.length,
    offset: 0,
    limit: 100,
    options_items: optionsItems,
    equity_items: equityItems,
  };
}

function makeOptionsPosition(
  id = 'pos-1',
  underlying = 'SPX',
  pnl = '500.00',
  overrides: Partial<PositionListResponse['options_items'][0]> = {},
): PositionListResponse['options_items'][0] {
  return {
    id,
    underlying,
    option_symbol: `${underlying} 2026-01-30 PUT 100`,
    strike: '100',
    expiry: '2026-01-30',
    option_type: 'PUT',
    direction: 'LONG',
    status: 'CLOSED',
    realized_pnl: pnl,
    is_covered_call: false,
    opened_at: '2026-01-01',
    closed_at: '2026-01-20',
    ...overrides,
  };
}

function makeEntry(label: string, totalPnl = '100.00', optionsPnl = '100.00', equityPnl = '0.00') {
  return {
    period_label: label,
    options_pnl: optionsPnl,
    equity_pnl: equityPnl,
    total_pnl: totalPnl,
  };
}

function makeSummary(
  items = [makeEntry('2026', '1250.00')],
  period = 'year',
  group_by: PnlGroupBy = 'underlying',
): PnlSummary {
  return { period, group_by, items };
}

function mockInputEvent(value: string): Event {
  return { target: { value } } as unknown as Event;
}

describe('PnlSummaryComponent', () => {
  let pnlServiceMock: jest.Mocked<Pick<PnlService, 'getSummary' | 'getPositionsForBucket'>>;

  beforeEach(async () => {
    pnlServiceMock = { getSummary: jest.fn(), getPositionsForBucket: jest.fn() };

    await TestBed.configureTestingModule({
      imports: [PnlSummaryComponent],
      providers: [{ provide: PnlService, useValue: pnlServiceMock }],
    })
      .overrideComponent(PnlSummaryComponent, {
        remove: { imports: [PositionDrawerComponent] },
        add: { imports: [MockPositionDrawerComponent] },
      })
      .compileComponents();
  });

  // ── 1. Initial state ──────────────────────────────────────────────────────────

  describe('initial state', () => {
    it('1. should create without error', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance).toBeTruthy();
    });

    it('2. should call getSummary with group_by=underlying and current-year dates on ngOnInit', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const year = new Date().getFullYear();
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith({
        group_by: 'underlying',
        closed_after: `${year}-01-01`,
        closed_before: `${year}-12-31`,
      });
    });

    it('3. should show loading state while request is in-flight', () => {
      const subject = new Subject<PnlSummary>();
      pnlServiceMock.getSummary.mockReturnValue(subject.asObservable());
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="loading-state"]'))).not.toBeNull();
      subject.complete();
    });
  });

  // ── 2. Successful load ────────────────────────────────────────────────────────

  describe('successful load', () => {
    it('4. should render P&L cards with correct count', () => {
      const items = [makeEntry('2025'), makeEntry('2026')];
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary(items)));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.queryAll(By.css('[data-testid="pnl-card"]')).length).toBe(2);
    });

    it('5. should display options_pnl, equity_pnl, total_pnl in first card', () => {
      const items = [makeEntry('2026', '1250.00', '1000.00', '250.00')];
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary(items)));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const card = fixture.debugElement.query(By.css('[data-testid="pnl-card"]'));
      expect(card.nativeElement.textContent).toContain('1000.00');
      expect(card.nativeElement.textContent).toContain('250.00');
      expect(card.nativeElement.textContent).toContain('1250.00');
    });

    it('6. should show empty state when items is []', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="empty-state"]'))).not.toBeNull();
      expect(fixture.debugElement.query(By.css('[data-testid="pnl-cards"]'))).toBeNull();
    });

    it('7. should show empty state when summary() is null', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.componentInstance.summary.set(null);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="empty-state"]'))).not.toBeNull();
    });

    it('7b. totalPnl returns "0.00" when summary has null items', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      fixture.componentInstance.summary.set({ period: 'year', items: null as unknown as [] });
      expect(fixture.componentInstance.totalPnl()).toBe('0.00');
    });
  });

  // ── 3. Error state ────────────────────────────────────────────────────────────

  describe('error state', () => {
    it('8. should show error state when API fails', () => {
      pnlServiceMock.getSummary.mockReturnValue(throwError(() => ({ message: 'API error' })));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="error-state"]'))).not.toBeNull();
    });

    it('9. should display error message', () => {
      pnlServiceMock.getSummary.mockReturnValue(throwError(() => ({ message: 'Load failed' })));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(
        fixture.debugElement.query(By.css('[data-testid="error-state"]')).nativeElement.textContent,
      ).toContain('Load failed');
    });

    it('10. should use fallback message when error has no message', () => {
      pnlServiceMock.getSummary.mockReturnValue(throwError(() => ({})));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.error()).toBe('Failed to load P&L summary.');
    });

    it('11. should call loadSummary again when Retry is clicked', () => {
      pnlServiceMock.getSummary.mockReturnValue(throwError(() => ({ message: 'err' })));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      fixture.debugElement.query(By.css('[data-testid="retry-btn"]')).nativeElement.click();
      expect(pnlServiceMock.getSummary).toHaveBeenCalledTimes(1);
    });
  });

  // ── 4. Time period dropdown ───────────────────────────────────────────────────

  describe('time period dropdown', () => {
    it('12. selectedTimePeriod defaults to "current-year"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.selectedTimePeriod()).toBe('current-year');
    });

    it('13. timePeriodOptions produces 11 options (6 fixed + 4 quarters + 1 custom)', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.timePeriodOptions().length).toBe(11);
    });

    it('14. timePeriodOptions includes rolling quarterly labels', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const quarterOptions = fixture.componentInstance
        .timePeriodOptions()
        .filter((o) => o.value.startsWith('q'));
      expect(quarterOptions.length).toBe(4);
    });

    it('15. timePeriodOptions includes "Current Year" option', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const opt = fixture.componentInstance
        .timePeriodOptions()
        .find((o) => o.value === 'current-year');
      expect(opt).toBeDefined();
      expect(opt!.label).toBe('Current Year');
    });

    it('16. timePeriodOptions includes "Custom" option with no dates', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const custom = fixture.componentInstance
        .timePeriodOptions()
        .find((o) => o.value === 'custom');
      expect(custom).toBeDefined();
      expect(custom!.closed_after).toBeUndefined();
      expect(custom!.closed_before).toBeUndefined();
    });

    it('17. time-period-select renders in DOM', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(
        fixture.debugElement.query(By.css('[data-testid="time-period-select"]')),
      ).not.toBeNull();
    });

    it('18. no period-toggle in DOM (regression — removed)', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="period-toggle"]'))).toBeNull();
    });

    it('19. no group-by-toggle in DOM (regression — removed)', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="group-by-toggle"]'))).toBeNull();
    });

    it('20. changing time period calls loadSummary', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));

      fixture.componentInstance.onTimePeriodChange({
        target: { value: 'last-30' },
      } as unknown as Event);
      expect(pnlServiceMock.getSummary).toHaveBeenCalledTimes(1);
    });

    it('21. selecting "Last 30 Days" sends correct closed_after/closed_before', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));

      fixture.componentInstance.onTimePeriodChange({
        target: { value: 'last-30' },
      } as unknown as Event);

      const call = pnlServiceMock.getSummary.mock.calls[0][0];
      expect(call).toHaveProperty('closed_after');
      expect(call).toHaveProperty('closed_before');
      expect(call!.closed_after).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(call!.closed_before).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    it('22. selecting "Custom" sends no date filters', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));

      fixture.componentInstance.onTimePeriodChange({
        target: { value: 'custom' },
      } as unknown as Event);

      const call = pnlServiceMock.getSummary.mock.calls[0][0];
      expect(call).not.toHaveProperty('closed_after');
      expect(call).not.toHaveProperty('closed_before');
    });

    it('23. card header shows ticker symbol', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const label = fixture.debugElement.query(By.css('[data-testid="pnl-card-label"]'));
      expect(label.nativeElement.textContent.trim()).toBe('SPX');
    });
  });

  // ── 5. Underlying filter ──────────────────────────────────────────────────────

  describe('underlying filter', () => {
    it('24. typing underlying calls getSummary with underlying param', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));

      fixture.componentInstance.onUnderlyingChange(mockInputEvent('NVDA'));
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith(
        expect.objectContaining({ underlying: 'NVDA' }),
      );
    });

    it('25. clearing underlying omits the param from getSummary call', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.onUnderlyingChange(mockInputEvent('NVDA'));
      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));

      fixture.componentInstance.onUnderlyingChange(mockInputEvent(''));
      const call = pnlServiceMock.getSummary.mock.calls[0][0];
      expect(call).not.toHaveProperty('underlying');
    });
  });

  // ── 6. P&L colouring ─────────────────────────────────────────────────────────

  describe('P&L card colouring', () => {
    it('26. positive total_pnl has pnl-positive class', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '500.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const total = fixture.debugElement.query(By.css('[data-testid="pnl-card-total"]'));
      expect(total.nativeElement.classList).toContain('pnl-positive');
    });

    it('27. negative total_pnl has pnl-negative class', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '-200.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const total = fixture.debugElement.query(By.css('[data-testid="pnl-card-total"]'));
      expect(total.nativeElement.classList).toContain('pnl-negative');
    });

    it('28. zero total_pnl has no special pnl class', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        of(makeSummary([makeEntry('2026', '0.00', '0.00', '0.00')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const total = fixture.debugElement.query(By.css('[data-testid="pnl-card-total"]'));
      expect(total.nativeElement.classList).not.toContain('pnl-positive');
      expect(total.nativeElement.classList).not.toContain('pnl-negative');
    });

    it('29. total-pnl headline has pnl-positive class when positive', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '500.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const total = fixture.debugElement.query(By.css('[data-testid="total-pnl"]'));
      expect(total.nativeElement.classList).toContain('pnl-positive');
    });

    it('30. pnlClass returns empty string for zero', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.pnlClass('0.00')).toBe('');
    });

    it('30b. options and equity pnl values have correct classes', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        of(makeSummary([makeEntry('2026', '750.00', '1000.00', '-250.00')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const options = fixture.debugElement.query(By.css('[data-testid="pnl-card-options"]'));
      const equity = fixture.debugElement.query(By.css('[data-testid="pnl-card-equity"]'));
      expect(options.nativeElement.classList).toContain('pnl-positive');
      expect(equity.nativeElement.classList).toContain('pnl-negative');
    });
  });

  // ── 7. Card structure ─────────────────────────────────────────────────────────

  describe('card layout structure', () => {
    it('31. pnl-cards container is rendered when data exists', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="pnl-cards"]'))).not.toBeNull();
    });

    it('32. each card has options, equity, and total metrics', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '500.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const card = fixture.debugElement.query(By.css('[data-testid="pnl-card"]'));
      expect(card.query(By.css('[data-testid="pnl-card-options"]'))).not.toBeNull();
      expect(card.query(By.css('[data-testid="pnl-card-equity"]'))).not.toBeNull();
      expect(card.query(By.css('[data-testid="pnl-card-total"]'))).not.toBeNull();
    });

    it('33. card label shows ticker without "Underlying" prefix', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const label = fixture.debugElement.query(By.css('[data-testid="pnl-card-label"]'));
      expect(label.nativeElement.textContent.trim()).toBe('SPX');
    });
  });

  // ── 8. Card expansion ─────────────────────────────────────────────────────────

  describe('card expansion', () => {
    it('34. toggleCard sets expandedLabel and calls getPositionsForBucket', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');

      expect(fixture.componentInstance.expandedLabel()).toBe('SPX');
      expect(pnlServiceMock.getPositionsForBucket).toHaveBeenCalledWith(
        expect.objectContaining({ period_label: 'SPX', group_by: 'underlying' }),
      );
    });

    it('35. toggleCard same label collapses card (expandedLabel becomes null)', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.componentInstance.toggleCard('SPX');

      expect(fixture.componentInstance.expandedLabel()).toBeNull();
      expect(fixture.componentInstance.bucketPositions()).toBeNull();
    });

    it('36. toggleCard different label switches expansion', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        of(makeSummary([makeEntry('NVDA'), makeEntry('SPX')])),
      );
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('NVDA');
      fixture.componentInstance.toggleCard('SPX');

      expect(fixture.componentInstance.expandedLabel()).toBe('SPX');
    });

    it('37. loadBucketPositions includes date-range params from selected time period', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');

      const year = new Date().getFullYear();
      expect(pnlServiceMock.getPositionsForBucket).toHaveBeenCalledWith(
        expect.objectContaining({
          closed_after: `${year}-01-01`,
          closed_before: `${year}-12-31`,
        }),
      );
    });

    it('37b. loadBucketPositions omits date params when Custom period is selected', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      // Switch to Custom (no dates)
      fixture.componentInstance.selectedTimePeriod.set('custom');
      fixture.componentInstance.toggleCard('SPX');

      const call = pnlServiceMock.getPositionsForBucket.mock.calls[0][0];
      expect(call).not.toHaveProperty('closed_after');
      expect(call).not.toHaveProperty('closed_before');
    });

    it('38. bucket-loading shows when positions are loading', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      const subject = new Subject<PositionListResponse>();
      pnlServiceMock.getPositionsForBucket.mockReturnValue(subject.asObservable());
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      expect(fixture.debugElement.query(By.css('[data-testid="bucket-loading"]'))).not.toBeNull();
      subject.complete();
    });

    it('39. bucket-error shows on fetch failure with retry button', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        throwError(() => ({ message: 'Network error' })),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      const errorEl = fixture.debugElement.query(By.css('[data-testid="bucket-error"]'));
      expect(errorEl).not.toBeNull();
      expect(errorEl.nativeElement.textContent).toContain('Network error');
      expect(fixture.debugElement.query(By.css('[data-testid="bucket-retry-btn"]'))).not.toBeNull();
    });

    it('40. retry button calls loadBucketPositions again', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(throwError(() => ({ message: 'err' })));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      pnlServiceMock.getPositionsForBucket.mockClear();
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      fixture.debugElement.query(By.css('[data-testid="bucket-retry-btn"]')).nativeElement.click();
      expect(pnlServiceMock.getPositionsForBucket).toHaveBeenCalledTimes(1);
    });

    it('41. bucket-empty shows when no positions returned', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      expect(fixture.debugElement.query(By.css('[data-testid="bucket-empty"]'))).not.toBeNull();
    });

    it('42. options positions table renders with correct row count', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(
          makeBucketResponse([makeOptionsPosition('pos-1'), makeOptionsPosition('pos-2', 'NVDA')]),
        ),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      expect(
        fixture.debugElement.query(By.css('[data-testid="bucket-options-table"]')),
      ).not.toBeNull();
      expect(fixture.debugElement.queryAll(By.css('[data-testid="bucket-pos-row"]')).length).toBe(
        2,
      );
    });

    it('43. position P&L value has correct pnl class for positive value', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(makeBucketResponse([makeOptionsPosition('pos-1', 'SPX', '500.00')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      const pnlCell = fixture.debugElement.query(By.css('[data-testid="bucket-pos-pnl"]'));
      expect(pnlCell.nativeElement.classList).toContain('pnl-positive');
    });

    it('44. position P&L value has correct pnl class for negative value', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(makeBucketResponse([makeOptionsPosition('pos-1', 'SPX', '-200.00')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      const pnlCell = fixture.debugElement.query(By.css('[data-testid="bucket-pos-pnl"]'));
      expect(pnlCell.nativeElement.classList).toContain('pnl-negative');
    });

    it('45. Legs button toggles position drawer open', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(makeBucketResponse([makeOptionsPosition('pos-1')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      expect(fixture.componentInstance.isPositionExpanded('pos-1')).toBe(false);
      fixture.componentInstance.togglePositionDrawer('pos-1');
      expect(fixture.componentInstance.isPositionExpanded('pos-1')).toBe(true);
    });

    it('45b. Legs button toggles position drawer closed when already open', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(makeBucketResponse([makeOptionsPosition('pos-1')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      fixture.componentInstance.togglePositionDrawer('pos-1');
      expect(fixture.componentInstance.isPositionExpanded('pos-1')).toBe(true);
      fixture.componentInstance.togglePositionDrawer('pos-1');
      expect(fixture.componentInstance.isPositionExpanded('pos-1')).toBe(false);
    });

    it('46. position-drawer appears in DOM when position is expanded', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(makeBucketResponse([makeOptionsPosition('pos-1')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      fixture.debugElement.query(By.css('[data-testid="bucket-expand-btn"]')).nativeElement.click();
      fixture.detectChanges();

      expect(fixture.debugElement.query(By.css('app-position-drawer'))).not.toBeNull();
    });
  });

  // ── 9. State reset on filter changes ─────────────────────────────────────────

  describe('state reset on filter changes', () => {
    it('47. expansion resets when time period changes', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      expect(fixture.componentInstance.expandedLabel()).toBe('SPX');

      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      fixture.componentInstance.onTimePeriodChange({
        target: { value: 'last-30' },
      } as unknown as Event);

      expect(fixture.componentInstance.expandedLabel()).toBeNull();
      expect(fixture.componentInstance.bucketPositions()).toBeNull();
    });

    it('48. expansion resets when underlying filter changes', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      expect(fixture.componentInstance.expandedLabel()).toBe('SPX');

      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      fixture.componentInstance.onUnderlyingChange({
        target: { value: 'NVDA' },
      } as unknown as Event);

      expect(fixture.componentInstance.expandedLabel()).toBeNull();
      expect(fixture.componentInstance.bucketPositions()).toBeNull();
    });
  });

  // ── 10. Expanded card DOM ─────────────────────────────────────────────────────

  describe('expanded card DOM', () => {
    it('49. expanded card has pnl-card--expanded class', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();

      const card = fixture.debugElement.query(By.css('[data-testid="pnl-card"]'));
      expect(card.nativeElement.classList).toContain('pnl-card--expanded');
    });

    it('50. expand indicator button shows in card header', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      expect(
        fixture.debugElement.query(By.css('[data-testid="pnl-card-expand-btn"]')),
      ).not.toBeNull();
    });

    it('51. bucketError uses fallback message when error has no message', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(throwError(() => ({})));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('SPX');

      expect(fixture.componentInstance.bucketError()).toBe('Failed to load positions.');
    });

    it('52. getPositionsForBucket includes underlying when underlying signal is set', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.underlying.set('SPX');
      fixture.componentInstance.toggleCard('SPX');

      expect(pnlServiceMock.getPositionsForBucket).toHaveBeenCalledWith(
        expect.objectContaining({ underlying: 'SPX' }),
      );
    });
  });

  // ── 11. daysHeld / daysToExpiry / isClosed helpers ───────────────────────────

  describe('daysHeld()', () => {
    it('53. returns correct number of days for a closed position', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const comp = fixture.componentInstance;
      expect(comp.daysHeld({ opened_at: '2026-01-01', closed_at: '2026-01-20' })).toBe(19);
    });

    it('54. returns null when opened_at is null', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(
        fixture.componentInstance.daysHeld({ opened_at: null, closed_at: '2026-01-20' }),
      ).toBeNull();
    });

    it('55. returns null when closed_at is null', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(
        fixture.componentInstance.daysHeld({ opened_at: '2026-01-01', closed_at: null }),
      ).toBeNull();
    });
  });

  describe('daysToExpiry()', () => {
    it('56. returns a number for a future expiry', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const futureExpiry = '2099-12-31';
      const result = fixture.componentInstance.daysToExpiry(futureExpiry);
      expect(result).not.toBeNull();
      expect(result!).toBeGreaterThan(0);
    });

    it('57. returns null for empty expiry string', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.daysToExpiry('')).toBeNull();
    });
  });

  describe('isClosed()', () => {
    it('58. returns true for CLOSED', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('CLOSED')).toBe(true);
    });

    it('59. returns true for EXPIRED', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('EXPIRED')).toBe(true);
    });

    it('60. returns true for ASSIGNED', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('ASSIGNED')).toBe(true);
    });

    it('61. returns true for EXERCISED', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('EXERCISED')).toBe(true);
    });

    it('62. returns false for OPEN', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('OPEN')).toBe(false);
    });

    it('63. returns false for PARTIALLY_CLOSED', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.isClosed('PARTIALLY_CLOSED')).toBe(false);
    });
  });

  // ── 12. Bucket table date/DTE/held columns ────────────────────────────────────

  describe('bucket table date columns', () => {
    function setupExpandedBucket(pos: PositionListResponse['options_items'][0]) {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('SPX')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse([pos])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      fixture.componentInstance.toggleCard('SPX');
      fixture.detectChanges();
      return fixture;
    }

    it('64. bucket table shows Opened column header', () => {
      const fixture = setupExpandedBucket(makeOptionsPosition());
      const headers = fixture.debugElement
        .query(By.css('[data-testid="bucket-options-table"]'))
        .queryAll(By.css('th'));
      const headerTexts = headers.map((h) => h.nativeElement.textContent.trim());
      expect(headerTexts).toContain('Opened');
    });

    it('65. bucket table shows Closed / DTE column header', () => {
      const fixture = setupExpandedBucket(makeOptionsPosition());
      const headers = fixture.debugElement
        .query(By.css('[data-testid="bucket-options-table"]'))
        .queryAll(By.css('th'));
      const headerTexts = headers.map((h) => h.nativeElement.textContent.trim());
      expect(headerTexts).toContain('Closed / DTE');
    });

    it('66. bucket table shows Held column header', () => {
      const fixture = setupExpandedBucket(makeOptionsPosition());
      const headers = fixture.debugElement
        .query(By.css('[data-testid="bucket-options-table"]'))
        .queryAll(By.css('th'));
      const headerTexts = headers.map((h) => h.nativeElement.textContent.trim());
      expect(headerTexts).toContain('Held');
    });

    it('67. closed position row shows opened_at date formatted', () => {
      const pos = makeOptionsPosition('pos-1', 'SPX', '100', {
        status: 'CLOSED',
        opened_at: '2026-01-01',
        closed_at: '2026-01-20',
      });
      const fixture = setupExpandedBucket(pos);
      const row = fixture.debugElement.query(By.css('[data-testid="bucket-pos-row"]'));
      expect(row.nativeElement.textContent).toContain('Jan 1, 2026');
    });

    it('68. closed position row shows closed_at date in Closed/DTE column', () => {
      const pos = makeOptionsPosition('pos-1', 'SPX', '100', {
        status: 'CLOSED',
        opened_at: '2026-01-01',
        closed_at: '2026-01-20',
      });
      const fixture = setupExpandedBucket(pos);
      const row = fixture.debugElement.query(By.css('[data-testid="bucket-pos-row"]'));
      expect(row.nativeElement.textContent).toContain('Jan 20, 2026');
    });

    it('69. closed position row shows days held', () => {
      const pos = makeOptionsPosition('pos-1', 'SPX', '100', {
        status: 'CLOSED',
        opened_at: '2026-01-01',
        closed_at: '2026-01-20',
      });
      const fixture = setupExpandedBucket(pos);
      const row = fixture.debugElement.query(By.css('[data-testid="bucket-pos-row"]'));
      expect(row.nativeElement.textContent).toContain('19d');
    });

    it('70. open position row shows days to expiry in Closed/DTE column', () => {
      const pos = makeOptionsPosition('pos-1', 'SPX', '100', {
        status: 'OPEN',
        opened_at: '2026-01-01',
        closed_at: null,
        expiry: '2099-12-31',
      });
      const fixture = setupExpandedBucket(pos);
      const row = fixture.debugElement.query(By.css('[data-testid="bucket-pos-row"]'));
      expect(row.nativeElement.textContent).toMatch(/\d+d/);
    });

    it('71. open position row shows em dash in Held column', () => {
      const pos = makeOptionsPosition('pos-1', 'SPX', '100', {
        status: 'OPEN',
        opened_at: '2026-01-01',
        closed_at: null,
        expiry: '2099-12-31',
      });
      const fixture = setupExpandedBucket(pos);
      const row = fixture.debugElement.query(By.css('[data-testid="bucket-pos-row"]'));
      expect(row.nativeElement.textContent).toContain('—');
    });

    it('72. null opened_at shows empty Opened cell', () => {
      const pos = makeOptionsPosition('pos-1', 'SPX', '100', {
        opened_at: null,
        closed_at: null,
        status: 'OPEN',
      });
      const fixture = setupExpandedBucket(pos);
      const row = fixture.debugElement.query(By.css('[data-testid="bucket-pos-row"]'));
      // opened_at null → DatePipe returns empty string, Held shows —
      expect(row.nativeElement.textContent).toContain('—');
    });
  });
});
