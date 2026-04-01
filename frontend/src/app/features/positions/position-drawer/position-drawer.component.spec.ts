import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Subject, of, throwError } from 'rxjs';
import { DatePipe } from '@angular/common';
import { PositionDrawerComponent } from './position-drawer.component';
import { PositionService } from '@core/services/position.service';
import { OptionsPositionDetail, OptionsPositionLeg } from '@core/models/position.model';

function makeLeg(overrides: Partial<OptionsPositionLeg> = {}): OptionsPositionLeg {
  return {
    id: 'leg-1',
    transaction_id: 'tx-1',
    leg_role: 'OPEN',
    quantity: '1',
    trade_date: '2026-03-01',
    price: '2.50',
    amount: '-250.00',
    commission: '0.65',
    ...overrides,
  };
}

function makeDetail(overrides: Partial<OptionsPositionDetail> = {}): OptionsPositionDetail {
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
    realized_pnl: '250.00',
    legs: [makeLeg()],
    total_realized_pnl: '250.00',
    ...overrides,
  };
}

describe('PositionDrawerComponent', () => {
  let positionServiceMock: jest.Mocked<Pick<PositionService, 'getPosition'>>;

  function createComponent(positionId = 'pos-1') {
    const fixture = TestBed.createComponent(PositionDrawerComponent);
    fixture.componentRef.setInput('positionId', positionId);
    return fixture;
  }

  beforeEach(async () => {
    positionServiceMock = {
      getPosition: jest.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [PositionDrawerComponent],
      providers: [
        { provide: PositionService, useValue: positionServiceMock },
        DatePipe,
      ],
    }).compileComponents();
  });

  // ── 1. Initial state / loading ────────────────────────────────────────────

  describe('initial state', () => {
    it('1. should create without error', () => {
      positionServiceMock.getPosition.mockReturnValue(of(makeDetail()));
      const fixture = createComponent();
      fixture.detectChanges();
      expect(fixture.componentInstance).toBeTruthy();
    });

    it('2. should call getPosition(positionId) on ngOnInit', () => {
      positionServiceMock.getPosition.mockReturnValue(of(makeDetail()));
      const fixture = createComponent('pos-42');
      fixture.detectChanges();
      expect(positionServiceMock.getPosition).toHaveBeenCalledWith('pos-42');
    });

    it('3. should show loading spinner while request is in-flight', () => {
      const subject = new Subject<OptionsPositionDetail>();
      positionServiceMock.getPosition.mockReturnValue(subject.asObservable());
      const fixture = createComponent();
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="drawer-loading"]'));
      expect(loading).not.toBeNull();
      subject.complete();
    });

    it('4. should not show content while loading', () => {
      const subject = new Subject<OptionsPositionDetail>();
      positionServiceMock.getPosition.mockReturnValue(subject.asObservable());
      const fixture = createComponent();
      fixture.detectChanges();
      const content = fixture.debugElement.query(By.css('[data-testid="drawer-content"]'));
      expect(content).toBeNull();
      subject.complete();
    });
  });

  // ── 2. Successful data load ───────────────────────────────────────────────

  describe('successful data load', () => {
    it('5. should render drawer-content after successful response', () => {
      positionServiceMock.getPosition.mockReturnValue(of(makeDetail()));
      const fixture = createComponent();
      fixture.detectChanges();
      const content = fixture.debugElement.query(By.css('[data-testid="drawer-content"]'));
      expect(content).not.toBeNull();
    });

    it('6. should render one leg row per leg in the response', () => {
      const detail = makeDetail({
        legs: [
          makeLeg({ id: 'leg-1', leg_role: 'OPEN' }),
          makeLeg({ id: 'leg-2', leg_role: 'CLOSE' }),
        ],
      });
      positionServiceMock.getPosition.mockReturnValue(of(detail));
      const fixture = createComponent();
      fixture.detectChanges();
      const rows = fixture.debugElement.queryAll(By.css('[data-testid^="leg-row-"]'));
      expect(rows.length).toBe(2);
    });

    it('7. should display leg_role OPEN in the role column', () => {
      const detail = makeDetail({ legs: [makeLeg({ id: 'leg-1', leg_role: 'OPEN' })] });
      positionServiceMock.getPosition.mockReturnValue(of(detail));
      const fixture = createComponent();
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="leg-row-leg-1"]'));
      expect(row.nativeElement.textContent).toContain('OPEN');
    });

    it('8. should display leg_role CLOSE in the role column', () => {
      const detail = makeDetail({ legs: [makeLeg({ id: 'leg-1', leg_role: 'CLOSE' })] });
      positionServiceMock.getPosition.mockReturnValue(of(detail));
      const fixture = createComponent();
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="leg-row-leg-1"]'));
      expect(row.nativeElement.textContent).toContain('CLOSE');
    });

    it('9. should show total_realized_pnl value when non-null', () => {
      positionServiceMock.getPosition.mockReturnValue(
        of(makeDetail({ total_realized_pnl: '350.00' })),
      );
      const fixture = createComponent();
      fixture.detectChanges();
      const pnlEl = fixture.debugElement.query(By.css('[data-testid="total-pnl"]'));
      expect(pnlEl.nativeElement.textContent.trim()).toBe('350.00');
    });

    it('10. should show "—" when total_realized_pnl is null', () => {
      positionServiceMock.getPosition.mockReturnValue(
        of(makeDetail({ total_realized_pnl: null })),
      );
      const fixture = createComponent();
      fixture.detectChanges();
      const pnlEl = fixture.debugElement.query(By.css('[data-testid="total-pnl"]'));
      expect(pnlEl.nativeElement.textContent.trim()).toBe('—');
    });

    it('11. should show "—" when leg price is null', () => {
      const detail = makeDetail({ legs: [makeLeg({ id: 'leg-1', price: null })] });
      positionServiceMock.getPosition.mockReturnValue(of(detail));
      const fixture = createComponent();
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="leg-row-leg-1"]'));
      expect(row.nativeElement.textContent).toContain('—');
    });

    it('12. should apply "positive" class to amount cell when amount is non-negative', () => {
      const detail = makeDetail({ legs: [makeLeg({ id: 'leg-1', amount: '250.00' })] });
      positionServiceMock.getPosition.mockReturnValue(of(detail));
      const fixture = createComponent();
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="leg-row-leg-1"]'));
      const amountCell: HTMLTableCellElement = row.nativeElement.querySelectorAll('td')[4];
      expect(amountCell.className).toContain('positive');
    });

    it('13. should apply "negative" class to amount cell when amount is negative', () => {
      const detail = makeDetail({ legs: [makeLeg({ id: 'leg-1', amount: '-250.00' })] });
      positionServiceMock.getPosition.mockReturnValue(of(detail));
      const fixture = createComponent();
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="leg-row-leg-1"]'));
      const amountCell: HTMLTableCellElement = row.nativeElement.querySelectorAll('td')[4];
      expect(amountCell.className).toContain('negative');
    });
  });

  // ── 3. Null detail state ──────────────────────────────────────────────────

  describe('null detail state', () => {
    it('14. should not show content when detail is null and loading is false', () => {
      const subject = new Subject<OptionsPositionDetail>();
      positionServiceMock.getPosition.mockReturnValue(subject.asObservable());
      const fixture = createComponent();
      fixture.detectChanges();
      // loading=true; manually set to false to reach the @else if (detail()) = false branch
      fixture.componentInstance.loading.set(false);
      fixture.detectChanges();
      const content = fixture.debugElement.query(By.css('[data-testid="drawer-content"]'));
      expect(content).toBeNull();
      subject.complete();
    });
  });

  // ── 4. Error handling ─────────────────────────────────────────────────────

  describe('error handling', () => {
    it('15. should show error state when getPosition fails', () => {
      positionServiceMock.getPosition.mockReturnValue(
        throwError(() => ({ message: 'Network error' })),
      );
      const fixture = createComponent();
      fixture.detectChanges();
      const errorEl = fixture.debugElement.query(By.css('[data-testid="drawer-error"]'));
      expect(errorEl).not.toBeNull();
      expect(errorEl.nativeElement.textContent).toContain('Network error');
    });

    it('16. should use fallback message when error has no message property', () => {
      positionServiceMock.getPosition.mockReturnValue(throwError(() => ({})));
      const fixture = createComponent();
      fixture.detectChanges();
      const errorEl = fixture.debugElement.query(By.css('[data-testid="drawer-error"]'));
      expect(errorEl.nativeElement.textContent).toContain('Failed to load position details.');
    });

    it('17. should call loadDetail again when retry button is clicked', () => {
      positionServiceMock.getPosition.mockReturnValue(
        throwError(() => ({ message: 'error' })),
      );
      const fixture = createComponent();
      fixture.detectChanges();

      positionServiceMock.getPosition.mockClear();
      positionServiceMock.getPosition.mockReturnValue(of(makeDetail()));

      const retryBtn = fixture.debugElement.query(By.css('[data-testid="drawer-retry-btn"]'));
      retryBtn.nativeElement.click();
      expect(positionServiceMock.getPosition).toHaveBeenCalledTimes(1);
    });

    it('18. should clear loading state after an error', () => {
      positionServiceMock.getPosition.mockReturnValue(
        throwError(() => ({ message: 'error' })),
      );
      const fixture = createComponent();
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="drawer-loading"]'));
      expect(loading).toBeNull();
    });
  });
});
