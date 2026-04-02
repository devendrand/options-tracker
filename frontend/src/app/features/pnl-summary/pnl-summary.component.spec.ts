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
  group_by: PnlGroupBy = 'period',
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

    it('2. should call getSummary with period=year and group_by=period on ngOnInit (defaults)', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith({
        period: 'year',
        group_by: 'period',
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

  // ── 4. Period toggle ──────────────────────────────────────────────────────────

  describe('period toggle', () => {
    it('12. year radio is checked by default', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const yearRadio: HTMLInputElement = fixture.debugElement.query(
        By.css('[data-testid="period-year"]'),
      ).nativeElement;
      expect(yearRadio.checked).toBe(true);
    });

    it('13. switching to Month calls getSummary with period=month', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([], 'month')));

      fixture.componentInstance.setPeriod('month');
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith(
        expect.objectContaining({ period: 'month' }),
      );
    });

    it('14. switching back to Year calls getSummary with period=year', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      fixture.componentInstance.setPeriod('month');

      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      fixture.componentInstance.setPeriod('year');
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith(
        expect.objectContaining({ period: 'year' }),
      );
    });
  });

  // ── 5. Period label formatting ────────────────────────────────────────────────

  describe('formatPeriodLabel()', () => {
    it('15. month period_label "2026-03" is displayed as "Mar 2026"', () => {
      const items = [makeEntry('2026-03', '500.00')];
      pnlServiceMock.getSummary.mockReturnValue(of({ period: 'month', items }));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.componentInstance.period.set('month');
      fixture.detectChanges();
      const label = fixture.debugElement.query(By.css('[data-testid="pnl-card-label"]'));
      expect(label.nativeElement.textContent).toContain('Mar 2026');
    });

    it('16. year period_label "2026" is displayed as "2026"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const label = fixture.debugElement.query(By.css('[data-testid="pnl-card-label"]'));
      expect(label.nativeElement.textContent).toContain('2026');
    });

    it('17. formatPeriodLabel with month="2026-12" returns "Dec 2026"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.formatPeriodLabel('2026-12', 'month', 'period')).toBe(
        'Dec 2026',
      );
    });

    it('18. formatPeriodLabel with year="2025" returns "2025"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.formatPeriodLabel('2025', 'year', 'period')).toBe('2025');
    });
  });

  // ── 6. Underlying filter ──────────────────────────────────────────────────────

  describe('underlying filter', () => {
    it('19. typing underlying calls getSummary with underlying param', () => {
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

    it('20. clearing underlying omits the param from getSummary call', () => {
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

  // ── 7. P&L colouring ─────────────────────────────────────────────────────────

  describe('P&L card colouring', () => {
    it('21. positive total_pnl has pnl-positive class', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '500.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const total = fixture.debugElement.query(By.css('[data-testid="pnl-card-total"]'));
      expect(total.nativeElement.classList).toContain('pnl-positive');
    });

    it('22. negative total_pnl has pnl-negative class', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '-200.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const total = fixture.debugElement.query(By.css('[data-testid="pnl-card-total"]'));
      expect(total.nativeElement.classList).toContain('pnl-negative');
    });

    it('23. zero total_pnl has no special pnl class', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        of(makeSummary([makeEntry('2026', '0.00', '0.00', '0.00')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const total = fixture.debugElement.query(By.css('[data-testid="pnl-card-total"]'));
      expect(total.nativeElement.classList).not.toContain('pnl-positive');
      expect(total.nativeElement.classList).not.toContain('pnl-negative');
    });

    it('24. total-pnl headline has pnl-positive class when positive', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '500.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const total = fixture.debugElement.query(By.css('[data-testid="total-pnl"]'));
      expect(total.nativeElement.classList).toContain('pnl-positive');
    });

    it('25. pnlClass returns empty string for zero', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.pnlClass('0.00')).toBe('');
    });

    it('25b. options and equity pnl values have correct classes', () => {
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

  // ── 8. Group-by toggle ────────────────────────────────────────────────────────

  describe('group-by toggle', () => {
    it('26. groupBy signal defaults to "period"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.groupBy()).toBe('period');
    });

    it('27. setGroupBy("underlying") calls getSummary with group_by=underlying', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([], 'year', 'underlying')));

      fixture.componentInstance.setGroupBy('underlying');
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith(
        expect.objectContaining({ group_by: 'underlying' }),
      );
    });

    it('29. loadSummary sends group_by param from signal', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([], 'year', 'underlying')));

      fixture.componentInstance.groupBy.set('underlying');
      fixture.componentInstance.loadSummary();
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith(
        expect.objectContaining({ group_by: 'underlying' }),
      );
    });

    it('30. underlying filter still works with group_by=underlying', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      fixture.componentInstance.setGroupBy('underlying');
      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));

      fixture.componentInstance.onUnderlyingChange(mockInputEvent('SPX'));
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith(
        expect.objectContaining({ group_by: 'underlying', underlying: 'SPX' }),
      );
    });
  });

  // ── 9. firstColumnHeader computed ────────────────────────────────────────────

  describe('firstColumnHeader()', () => {
    it('31. returns "Period" when groupBy is "period"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.firstColumnHeader()).toBe('Period');
    });

    it('32. returns "Underlying" when groupBy is "underlying"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      fixture.componentInstance.groupBy.set('underlying');
      expect(fixture.componentInstance.firstColumnHeader()).toBe('Underlying');
    });
  });

  // ── 10. formatPeriodLabel with groupBy ────────────────────────────────────────

  describe('formatPeriodLabel() with groupBy', () => {
    it('34. returns label as-is when groupBy is "underlying"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.formatPeriodLabel('SPX', 'month', 'underlying')).toBe('SPX');
    });
  });

  // ── 11. periodDisabled computed ───────────────────────────────────────────────

  describe('periodDisabled()', () => {
    it('36. is false by default (groupBy=period)', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.periodDisabled()).toBe(false);
    });

    it('37. is true when groupBy is "underlying"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      fixture.componentInstance.groupBy.set('underlying');
      expect(fixture.componentInstance.periodDisabled()).toBe(true);
    });
  });

  // ── 12. Group-by DOM / HTML ───────────────────────────────────────────────────

  describe('group-by toggle DOM', () => {
    it('39. group-by-toggle container is rendered', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="group-by-toggle"]'))).not.toBeNull();
    });

    it('40. group-by-period radio is checked by default', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const radio: HTMLInputElement = fixture.debugElement.query(
        By.css('[data-testid="group-by-period"]'),
      ).nativeElement;
      expect(radio.checked).toBe(true);
    });

    it('41. period toggle radios are disabled when groupBy is "underlying"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      fixture.componentInstance.groupBy.set('underlying');
      fixture.detectChanges();
      const yearRadio: HTMLInputElement = fixture.debugElement.query(
        By.css('[data-testid="period-year"]'),
      ).nativeElement;
      const monthRadio: HTMLInputElement = fixture.debugElement.query(
        By.css('[data-testid="period-month"]'),
      ).nativeElement;
      expect(yearRadio.disabled).toBe(true);
      expect(monthRadio.disabled).toBe(true);
    });

    it('42. period toggle re-enabled after switching from "underlying" back to "period"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.groupBy.set('underlying');
      fixture.detectChanges();
      fixture.componentInstance.setGroupBy('period');
      fixture.detectChanges();

      const yearRadio: HTMLInputElement = fixture.debugElement.query(
        By.css('[data-testid="period-year"]'),
      ).nativeElement;
      expect(yearRadio.disabled).toBe(false);
    });

    it('43. card header shows "Underlying" label when groupBy is "underlying"', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        of(makeSummary([makeEntry('SPX')], 'year', 'underlying')),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.componentInstance.groupBy.set('underlying');
      fixture.detectChanges();
      const label = fixture.debugElement.query(By.css('[data-testid="pnl-card-label"]'));
      expect(label.nativeElement.textContent).toContain('Underlying');
      expect(label.nativeElement.textContent).toContain('SPX');
    });
  });

  // ── 13. Card structure ────────────────────────────────────────────────────────

  describe('card layout structure', () => {
    it('44. pnl-cards container is rendered when data exists', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="pnl-cards"]'))).not.toBeNull();
    });

    it('45. each card has options, equity, and total metrics', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '500.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const card = fixture.debugElement.query(By.css('[data-testid="pnl-card"]'));
      expect(card.query(By.css('[data-testid="pnl-card-options"]'))).not.toBeNull();
      expect(card.query(By.css('[data-testid="pnl-card-equity"]'))).not.toBeNull();
      expect(card.query(By.css('[data-testid="pnl-card-total"]'))).not.toBeNull();
    });

    it('46. card label shows period header text', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const label = fixture.debugElement.query(By.css('[data-testid="pnl-card-label"]'));
      expect(label.nativeElement.textContent).toContain('Period');
      expect(label.nativeElement.textContent).toContain('2026');
    });
  });

  // ── 14. Card expansion ────────────────────────────────────────────────────────

  describe('card expansion', () => {
    it('47. toggleCard sets expandedLabel and calls getPositionsForBucket', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');

      expect(fixture.componentInstance.expandedLabel()).toBe('2026');
      expect(pnlServiceMock.getPositionsForBucket).toHaveBeenCalledWith(
        expect.objectContaining({ period_label: '2026', period: 'year', group_by: 'period' }),
      );
    });

    it('48. toggleCard same label collapses card (expandedLabel becomes null)', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.componentInstance.toggleCard('2026');

      expect(fixture.componentInstance.expandedLabel()).toBeNull();
      expect(fixture.componentInstance.bucketPositions()).toBeNull();
    });

    it('49. toggleCard different label switches expansion', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        of(makeSummary([makeEntry('2025'), makeEntry('2026')])),
      );
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2025');
      fixture.componentInstance.toggleCard('2026');

      expect(fixture.componentInstance.expandedLabel()).toBe('2026');
    });

    it('50. bucket-loading shows when positions are loading', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      const subject = new Subject<PositionListResponse>();
      pnlServiceMock.getPositionsForBucket.mockReturnValue(subject.asObservable());
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      expect(fixture.debugElement.query(By.css('[data-testid="bucket-loading"]'))).not.toBeNull();
      subject.complete();
    });

    it('51. bucket-error shows on fetch failure with retry button', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        throwError(() => ({ message: 'Network error' })),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      const errorEl = fixture.debugElement.query(By.css('[data-testid="bucket-error"]'));
      expect(errorEl).not.toBeNull();
      expect(errorEl.nativeElement.textContent).toContain('Network error');
      expect(fixture.debugElement.query(By.css('[data-testid="bucket-retry-btn"]'))).not.toBeNull();
    });

    it('52. retry button calls loadBucketPositions again', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(throwError(() => ({ message: 'err' })));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      pnlServiceMock.getPositionsForBucket.mockClear();
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      fixture.debugElement.query(By.css('[data-testid="bucket-retry-btn"]')).nativeElement.click();
      expect(pnlServiceMock.getPositionsForBucket).toHaveBeenCalledTimes(1);
    });

    it('53. bucket-empty shows when no positions returned', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      expect(fixture.debugElement.query(By.css('[data-testid="bucket-empty"]'))).not.toBeNull();
    });

    it('54. options positions table renders with correct row count', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(
          makeBucketResponse([makeOptionsPosition('pos-1'), makeOptionsPosition('pos-2', 'NVDA')]),
        ),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      expect(
        fixture.debugElement.query(By.css('[data-testid="bucket-options-table"]')),
      ).not.toBeNull();
      expect(fixture.debugElement.queryAll(By.css('[data-testid="bucket-pos-row"]')).length).toBe(
        2,
      );
    });

    it('55. position P&L value has correct pnl class for positive value', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(makeBucketResponse([makeOptionsPosition('pos-1', 'SPX', '500.00')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      const pnlCell = fixture.debugElement.query(By.css('[data-testid="bucket-pos-pnl"]'));
      expect(pnlCell.nativeElement.classList).toContain('pnl-positive');
    });

    it('56. position P&L value has correct pnl class for negative value', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(makeBucketResponse([makeOptionsPosition('pos-1', 'SPX', '-200.00')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      const pnlCell = fixture.debugElement.query(By.css('[data-testid="bucket-pos-pnl"]'));
      expect(pnlCell.nativeElement.classList).toContain('pnl-negative');
    });

    it('57. Legs button toggles position drawer open', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(makeBucketResponse([makeOptionsPosition('pos-1')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      expect(fixture.componentInstance.isPositionExpanded('pos-1')).toBe(false);
      fixture.componentInstance.togglePositionDrawer('pos-1');
      expect(fixture.componentInstance.isPositionExpanded('pos-1')).toBe(true);
    });

    it('57b. Legs button toggles position drawer closed when already open', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(makeBucketResponse([makeOptionsPosition('pos-1')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      fixture.componentInstance.togglePositionDrawer('pos-1');
      expect(fixture.componentInstance.isPositionExpanded('pos-1')).toBe(true);
      fixture.componentInstance.togglePositionDrawer('pos-1');
      expect(fixture.componentInstance.isPositionExpanded('pos-1')).toBe(false);
    });

    it('58. position-drawer appears in DOM when position is expanded', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(
        of(makeBucketResponse([makeOptionsPosition('pos-1')])),
      );
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      fixture.debugElement.query(By.css('[data-testid="bucket-expand-btn"]')).nativeElement.click();
      fixture.detectChanges();

      expect(fixture.debugElement.query(By.css('app-position-drawer'))).not.toBeNull();
    });
  });

  // ── 15. State reset on filter changes ────────────────────────────────────────

  describe('state reset on filter changes', () => {
    it('59. expansion resets when setPeriod is called', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      expect(fixture.componentInstance.expandedLabel()).toBe('2026');

      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([], 'month')));
      fixture.componentInstance.setPeriod('month');

      expect(fixture.componentInstance.expandedLabel()).toBeNull();
      expect(fixture.componentInstance.bucketPositions()).toBeNull();
    });

    it('60. expansion resets when setGroupBy is called', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      expect(fixture.componentInstance.expandedLabel()).toBe('2026');

      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([], 'year', 'underlying')));
      fixture.componentInstance.setGroupBy('underlying');

      expect(fixture.componentInstance.expandedLabel()).toBeNull();
      expect(fixture.componentInstance.bucketPositions()).toBeNull();
    });

    it('61. expansion resets when underlying filter changes', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      expect(fixture.componentInstance.expandedLabel()).toBe('2026');

      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      fixture.componentInstance.onUnderlyingChange({
        target: { value: 'SPX' },
      } as unknown as Event);

      expect(fixture.componentInstance.expandedLabel()).toBeNull();
      expect(fixture.componentInstance.bucketPositions()).toBeNull();
    });
  });

  // ── 16. Expanded card DOM ─────────────────────────────────────────────────────

  describe('expanded card DOM', () => {
    it('62. expanded card has pnl-card--expanded class', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');
      fixture.detectChanges();

      const card = fixture.debugElement.query(By.css('[data-testid="pnl-card"]'));
      expect(card.nativeElement.classList).toContain('pnl-card--expanded');
    });

    it('63. expand indicator button shows in card header', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      expect(
        fixture.debugElement.query(By.css('[data-testid="pnl-card-expand-btn"]')),
      ).not.toBeNull();
    });

    it('64. bucketError uses fallback message when error has no message', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(throwError(() => ({})));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.toggleCard('2026');

      expect(fixture.componentInstance.bucketError()).toBe('Failed to load positions.');
    });

    it('65. getPositionsForBucket includes underlying when underlying signal is set', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      pnlServiceMock.getPositionsForBucket.mockReturnValue(of(makeBucketResponse()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();

      fixture.componentInstance.underlying.set('SPX');
      fixture.componentInstance.toggleCard('2026');

      expect(pnlServiceMock.getPositionsForBucket).toHaveBeenCalledWith(
        expect.objectContaining({ underlying: 'SPX' }),
      );
    });
  });
});
