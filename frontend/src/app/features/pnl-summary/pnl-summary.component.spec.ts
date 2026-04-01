import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Subject, of, throwError } from 'rxjs';
import { PnlSummaryComponent } from './pnl-summary.component';
import { PnlService } from '@core/services/pnl.service';
import { PnlSummary } from '@core/models/pnl.model';

function makeEntry(label: string, totalPnl = '100.00', optionsPnl = '100.00', equityPnl = '0.00') {
  return {
    period_label: label,
    options_pnl: optionsPnl,
    equity_pnl: equityPnl,
    total_pnl: totalPnl,
  };
}

function makeSummary(items = [makeEntry('2026', '1250.00')], period = 'year'): PnlSummary {
  return { period, items };
}

function mockInputEvent(value: string): Event {
  return { target: { value } } as unknown as Event;
}

describe('PnlSummaryComponent', () => {
  let pnlServiceMock: jest.Mocked<Pick<PnlService, 'getSummary'>>;

  beforeEach(async () => {
    pnlServiceMock = { getSummary: jest.fn() };

    await TestBed.configureTestingModule({
      imports: [PnlSummaryComponent],
      providers: [{ provide: PnlService, useValue: pnlServiceMock }],
    }).compileComponents();
  });

  // ── 1. Initial state ──────────────────────────────────────────────────────────

  describe('initial state', () => {
    it('1. should create without error', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance).toBeTruthy();
    });

    it('2. should call getSummary with period=year on ngOnInit (default)', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith({ period: 'year' });
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
    it('4. should render P&L table with correct number of rows', () => {
      const items = [makeEntry('2025'), makeEntry('2026')];
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary(items)));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.queryAll(By.css('[data-testid="pnl-row"]')).length).toBe(2);
    });

    it('5. should display options_pnl, equity_pnl, total_pnl in first row', () => {
      const items = [makeEntry('2026', '1250.00', '1000.00', '250.00')];
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary(items)));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="pnl-row"]'));
      expect(row.nativeElement.textContent).toContain('1250.00');
      expect(row.nativeElement.textContent).toContain('1000.00');
      expect(row.nativeElement.textContent).toContain('250.00');
    });

    it('6. should show empty state when items is []', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="empty-state"]'))).not.toBeNull();
      expect(fixture.debugElement.query(By.css('[data-testid="pnl-table"]'))).toBeNull();
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
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith({ period: 'month' });
    });

    it('14. switching back to Year calls getSummary with period=year', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      fixture.componentInstance.setPeriod('month');

      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      fixture.componentInstance.setPeriod('year');
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith({ period: 'year' });
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
      const row = fixture.debugElement.query(By.css('[data-testid="pnl-row"]'));
      expect(row.nativeElement.textContent).toContain('Mar 2026');
    });

    it('16. year period_label "2026" is displayed as "2026"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="pnl-row"]'));
      expect(row.nativeElement.textContent).toContain('2026');
    });

    it('17. formatPeriodLabel with month="2026-12" returns "Dec 2026"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.formatPeriodLabel('2026-12', 'month')).toBe('Dec 2026');
    });

    it('18. formatPeriodLabel with year="2025" returns "2025"', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary()));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance.formatPeriodLabel('2025', 'year')).toBe('2025');
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

  describe('P&L row colouring', () => {
    it('21. positive total_pnl row cell has pnl-positive class', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '500.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const cells = fixture.debugElement.queryAll(By.css('[data-testid="pnl-row"] td'));
      // Total P&L is the 4th cell (index 3)
      expect(cells[3].nativeElement.classList).toContain('pnl-positive');
    });

    it('22. negative total_pnl row cell has pnl-negative class', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '-200.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const cells = fixture.debugElement.queryAll(By.css('[data-testid="pnl-row"] td'));
      expect(cells[3].nativeElement.classList).toContain('pnl-negative');
    });

    it('23. zero total_pnl row cell has no special class', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makeSummary([makeEntry('2026', '0.00')])));
      const fixture = TestBed.createComponent(PnlSummaryComponent);
      fixture.detectChanges();
      const cells = fixture.debugElement.queryAll(By.css('[data-testid="pnl-row"] td'));
      expect(cells[3].nativeElement.className.trim()).toBe('align-right');
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
  });
});
