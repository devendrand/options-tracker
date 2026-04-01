import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Subject, of, throwError } from 'rxjs';
import { provideRouter } from '@angular/router';
import { DashboardComponent } from './dashboard.component';
import { PnlService } from '@core/services/pnl.service';
import { PositionService } from '@core/services/position.service';
import { UploadService } from '@core/services/upload.service';
import { PnlSummary, PnlPeriodEntry } from '@core/models/pnl.model';
import { Upload, UploadListResponse } from '@core/models/upload.model';
import { PositionListResponse } from '@core/models/position.model';

function makePnlEntry(overrides: Partial<PnlPeriodEntry> = {}): PnlPeriodEntry {
  return {
    period_label: '2026-01',
    options_pnl: '100.00',
    equity_pnl: '0.00',
    total_pnl: '100.00',
    ...overrides,
  };
}

function makePnlSummary(items: PnlPeriodEntry[] = [makePnlEntry()]): PnlSummary {
  return { period: 'year', items };
}

function makePositionListResponse(total: number): PositionListResponse {
  return { total, offset: 0, limit: 1, options_items: [], equity_items: [] };
}

function makeUpload(id: string, filename = `upload-${id}.csv`): Upload {
  return {
    id,
    filename,
    status: 'COMPLETED',
    broker: 'ETRADE',
    row_count: 10,
    options_count: 5,
    duplicate_count: 0,
    possible_duplicate_count: 0,
    parse_error_count: 0,
    internal_transfer_count: 0,
    uploaded_at: '2026-03-01T00:00:00Z',
  };
}

function makeUploadListResponse(items: Upload[]): UploadListResponse {
  return { items, total: items.length, offset: 0, limit: 100 };
}

describe('DashboardComponent', () => {
  let pnlServiceMock: jest.Mocked<Pick<PnlService, 'getSummary'>>;
  let positionServiceMock: jest.Mocked<Pick<PositionService, 'getPositions'>>;
  let uploadServiceMock: jest.Mocked<Pick<UploadService, 'getUploads'>>;

  function setupDefaultMocks() {
    pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary()));
    positionServiceMock.getPositions
      .mockReturnValueOnce(of(makePositionListResponse(5)))
      .mockReturnValueOnce(of(makePositionListResponse(12)));
    uploadServiceMock.getUploads.mockReturnValue(
      of(makeUploadListResponse([makeUpload('u1'), makeUpload('u2')])),
    );
  }

  function createComponent() {
    return TestBed.createComponent(DashboardComponent);
  }

  beforeEach(async () => {
    pnlServiceMock = { getSummary: jest.fn() };
    positionServiceMock = { getPositions: jest.fn() };
    uploadServiceMock = { getUploads: jest.fn() };

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        { provide: PnlService, useValue: pnlServiceMock },
        { provide: PositionService, useValue: positionServiceMock },
        { provide: UploadService, useValue: uploadServiceMock },
        provideRouter([]),
      ],
    }).compileComponents();
  });

  // ── 1. Initialisation ─────────────────────────────────────────────────────

  describe('initialisation', () => {
    it('1. should create without error', () => {
      setupDefaultMocks();
      const fixture = createComponent();
      fixture.detectChanges();
      expect(fixture.componentInstance).toBeTruthy();
    });

    it('2. should call getSummary, getPositions (x2), and getUploads on init', () => {
      setupDefaultMocks();
      const fixture = createComponent();
      fixture.detectChanges();
      expect(pnlServiceMock.getSummary).toHaveBeenCalledWith({ period: 'year' });
      expect(positionServiceMock.getPositions).toHaveBeenCalledTimes(2);
      expect(positionServiceMock.getPositions).toHaveBeenCalledWith({
        status: 'OPEN',
        limit: 1,
      });
      expect(positionServiceMock.getPositions).toHaveBeenCalledWith({
        status: 'CLOSED',
        limit: 1,
      });
      expect(uploadServiceMock.getUploads).toHaveBeenCalledTimes(1);
    });

    it('3. should show no-data-cta before any data has loaded (hasData=false)', () => {
      const pnlSubject = new Subject<PnlSummary>();
      const openSubject = new Subject<PositionListResponse>();
      const closedSubject = new Subject<PositionListResponse>();
      const uploadsSubject = new Subject<UploadListResponse>();
      pnlServiceMock.getSummary.mockReturnValue(pnlSubject.asObservable());
      positionServiceMock.getPositions
        .mockReturnValueOnce(openSubject.asObservable())
        .mockReturnValueOnce(closedSubject.asObservable());
      uploadServiceMock.getUploads.mockReturnValue(uploadsSubject.asObservable());
      const fixture = createComponent();
      fixture.detectChanges();
      const cta = fixture.debugElement.query(By.css('[data-testid="no-data-cta"]'));
      expect(cta).not.toBeNull();
      pnlSubject.complete();
      openSubject.complete();
      closedSubject.complete();
      uploadsSubject.complete();
    });
  });

  // ── 2. P&L section ────────────────────────────────────────────────────────

  describe('P&L section', () => {
    it('4. should show pnl-loading while request is in-flight', () => {
      const subject = new Subject<PnlSummary>();
      pnlServiceMock.getSummary.mockReturnValue(subject.asObservable());
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="pnl-loading"]'));
      expect(loading).not.toBeNull();
      subject.complete();
    });

    it('5. should not show pnl-value while pnl is loading', () => {
      const subject = new Subject<PnlSummary>();
      pnlServiceMock.getSummary.mockReturnValue(subject.asObservable());
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const pnlValue = fixture.debugElement.query(By.css('[data-testid="pnl-value"]'));
      expect(pnlValue).toBeNull();
      subject.complete();
    });

    it('6. should show pnl-value after successful load', () => {
      setupDefaultMocks();
      const fixture = createComponent();
      fixture.detectChanges();
      const pnlValue = fixture.debugElement.query(By.css('[data-testid="pnl-value"]'));
      expect(pnlValue).not.toBeNull();
    });

    it('7. totalPnl sums item total_pnl values correctly', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        of(
          makePnlSummary([
            makePnlEntry({ total_pnl: '100.00' }),
            makePnlEntry({ total_pnl: '50.50' }),
          ]),
        ),
      );
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(1)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const pnlValue = fixture.debugElement.query(By.css('[data-testid="pnl-value"]'));
      expect(pnlValue.nativeElement.textContent.trim()).toBe('150.50');
    });

    it('8. totalPnl is "0.00" when summary has no items', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const pnlValue = fixture.debugElement.query(By.css('[data-testid="pnl-value"]'));
      expect(pnlValue.nativeElement.textContent.trim()).toBe('0.00');
    });

    it('9. pnl-value has "positive" class when total > 0', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        of(makePnlSummary([makePnlEntry({ total_pnl: '250.00' })])),
      );
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(1)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const pnlValue = fixture.debugElement.query(By.css('[data-testid="pnl-value"]'));
      expect(pnlValue.nativeElement.classList).toContain('positive');
      expect(pnlValue.nativeElement.classList).not.toContain('negative');
    });

    it('10. pnl-value has "negative" class when total < 0', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        of(makePnlSummary([makePnlEntry({ total_pnl: '-75.00' })])),
      );
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(1)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const pnlValue = fixture.debugElement.query(By.css('[data-testid="pnl-value"]'));
      expect(pnlValue.nativeElement.classList).toContain('negative');
      expect(pnlValue.nativeElement.classList).not.toContain('positive');
    });

    it('11. pnl-value has neither "positive" nor "negative" class when total is 0', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        of(makePnlSummary([makePnlEntry({ total_pnl: '0.00' })])),
      );
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const pnlValue = fixture.debugElement.query(By.css('[data-testid="pnl-value"]'));
      expect(pnlValue.nativeElement.classList).not.toContain('positive');
      expect(pnlValue.nativeElement.classList).not.toContain('negative');
    });

    it('12. should show pnl-error when getSummary fails', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        throwError(() => ({ message: 'Network error' })),
      );
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const errEl = fixture.debugElement.query(By.css('[data-testid="pnl-error"]'));
      expect(errEl).not.toBeNull();
      expect(errEl.nativeElement.textContent).toContain('Network error');
    });

    it('13. should use fallback pnl-error message when error has no message', () => {
      pnlServiceMock.getSummary.mockReturnValue(throwError(() => ({})));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const errEl = fixture.debugElement.query(By.css('[data-testid="pnl-error"]'));
      expect(errEl.nativeElement.textContent).toContain('Failed to load P&L summary.');
    });

    it('14. should call loadPnl again when pnl retry button is clicked', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        throwError(() => ({ message: 'error' })),
      );
      positionServiceMock.getPositions
        .mockReturnValue(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();

      pnlServiceMock.getSummary.mockClear();
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary()));

      const retryBtn = fixture.debugElement.query(By.css('[data-testid="pnl-retry-btn"]'));
      retryBtn.nativeElement.click();
      expect(pnlServiceMock.getSummary).toHaveBeenCalledTimes(1);
    });

    it('15. should clear pnl-loading after an error', () => {
      pnlServiceMock.getSummary.mockReturnValue(
        throwError(() => ({ message: 'error' })),
      );
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="pnl-loading"]'));
      expect(loading).toBeNull();
    });
  });

  // ── 3. Counts section ─────────────────────────────────────────────────────

  describe('counts section', () => {
    it('16. should show counts-loading while request is in-flight', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      const openSubject = new Subject<PositionListResponse>();
      const closedSubject = new Subject<PositionListResponse>();
      positionServiceMock.getPositions
        .mockReturnValueOnce(openSubject.asObservable())
        .mockReturnValueOnce(closedSubject.asObservable());
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="counts-loading"]'));
      expect(loading).not.toBeNull();
      openSubject.complete();
      closedSubject.complete();
    });

    it('17. should not show open-count while counts are loading', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      const openSubject = new Subject<PositionListResponse>();
      const closedSubject = new Subject<PositionListResponse>();
      positionServiceMock.getPositions
        .mockReturnValueOnce(openSubject.asObservable())
        .mockReturnValueOnce(closedSubject.asObservable());
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const openCount = fixture.debugElement.query(By.css('[data-testid="open-count"]'));
      expect(openCount).toBeNull();
      openSubject.complete();
      closedSubject.complete();
    });

    it('18. should show open-count after successful counts load', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(7)))
        .mockReturnValueOnce(of(makePositionListResponse(3)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const openCount = fixture.debugElement.query(By.css('[data-testid="open-count"]'));
      expect(openCount.nativeElement.textContent.trim()).toBe('7');
    });

    it('19. should show closed-count after successful counts load', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(7)))
        .mockReturnValueOnce(of(makePositionListResponse(3)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const closedCount = fixture.debugElement.query(By.css('[data-testid="closed-count"]'));
      expect(closedCount.nativeElement.textContent.trim()).toBe('3');
    });

    it('20. should show counts-error when getPositions fails', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions.mockReturnValue(
        throwError(() => ({ message: 'Counts failed' })),
      );
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const errEl = fixture.debugElement.query(By.css('[data-testid="counts-error"]'));
      expect(errEl).not.toBeNull();
      expect(errEl.nativeElement.textContent).toContain('Counts failed');
    });

    it('21. should use fallback counts-error message when error has no message', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions.mockReturnValue(throwError(() => ({})));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const errEl = fixture.debugElement.query(By.css('[data-testid="counts-error"]'));
      expect(errEl.nativeElement.textContent).toContain('Failed to load position counts.');
    });

    it('22. should call loadCounts again when counts retry button is clicked', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions.mockReturnValue(
        throwError(() => ({ message: 'error' })),
      );
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();

      positionServiceMock.getPositions.mockClear();
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(2)))
        .mockReturnValueOnce(of(makePositionListResponse(1)));

      const retryBtn = fixture.debugElement.query(By.css('[data-testid="counts-retry-btn"]'));
      retryBtn.nativeElement.click();
      expect(positionServiceMock.getPositions).toHaveBeenCalledTimes(2);
    });

    it('23. should clear counts-loading after an error', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions.mockReturnValue(
        throwError(() => ({ message: 'error' })),
      );
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="counts-loading"]'));
      expect(loading).toBeNull();
    });
  });

  // ── 4. Uploads section ────────────────────────────────────────────────────

  describe('uploads section', () => {
    it('24. should show uploads-loading while request is in-flight', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      const subject = new Subject<UploadListResponse>();
      uploadServiceMock.getUploads.mockReturnValue(subject.asObservable());
      const fixture = createComponent();
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="uploads-loading"]'));
      expect(loading).not.toBeNull();
      subject.complete();
    });

    it('25. should show uploads-empty when no uploads exist', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const empty = fixture.debugElement.query(By.css('[data-testid="uploads-empty"]'));
      expect(empty).not.toBeNull();
    });

    it('26. should show upload links when uploads exist', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(
        of(makeUploadListResponse([makeUpload('a'), makeUpload('b'), makeUpload('c')])),
      );
      const fixture = createComponent();
      fixture.detectChanges();
      const links = fixture.debugElement.queryAll(By.css('[data-testid^="upload-link-"]'));
      expect(links.length).toBe(3);
      expect(links[0].nativeElement.textContent.trim()).toBe('upload-a.csv');
    });

    it('27. should limit upload links to 5', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      const manyUploads = ['1', '2', '3', '4', '5', '6', '7'].map(makeUpload);
      uploadServiceMock.getUploads.mockReturnValue(
        of(makeUploadListResponse(manyUploads)),
      );
      const fixture = createComponent();
      fixture.detectChanges();
      const links = fixture.debugElement.queryAll(By.css('[data-testid^="upload-link-"]'));
      expect(links.length).toBe(5);
    });

    it('28. should show uploads-error when getUploads fails', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(
        throwError(() => ({ message: 'Uploads failed' })),
      );
      const fixture = createComponent();
      fixture.detectChanges();
      const errEl = fixture.debugElement.query(By.css('[data-testid="uploads-error"]'));
      expect(errEl).not.toBeNull();
      expect(errEl.nativeElement.textContent).toContain('Uploads failed');
    });

    it('29. should use fallback uploads-error message when error has no message', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(throwError(() => ({})));
      const fixture = createComponent();
      fixture.detectChanges();
      const errEl = fixture.debugElement.query(By.css('[data-testid="uploads-error"]'));
      expect(errEl.nativeElement.textContent).toContain('Failed to load recent uploads.');
    });

    it('30. should call loadRecentUploads again when uploads retry button is clicked', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(
        throwError(() => ({ message: 'error' })),
      );
      const fixture = createComponent();
      fixture.detectChanges();

      uploadServiceMock.getUploads.mockClear();
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));

      const retryBtn = fixture.debugElement.query(
        By.css('[data-testid="uploads-retry-btn"]'),
      );
      retryBtn.nativeElement.click();
      expect(uploadServiceMock.getUploads).toHaveBeenCalledTimes(1);
    });

    it('31. should clear uploads-loading after an error', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(throwError(() => ({ message: 'err' })));
      const fixture = createComponent();
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="uploads-loading"]'));
      expect(loading).toBeNull();
    });
  });

  // ── 5. hasData / no-data-cta ──────────────────────────────────────────────

  describe('hasData and no-data-cta', () => {
    it('32. should hide no-data-cta when openCount > 0', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(3)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const cta = fixture.debugElement.query(By.css('[data-testid="no-data-cta"]'));
      expect(cta).toBeNull();
    });

    it('33. should hide no-data-cta when closedCount > 0', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(8)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const cta = fixture.debugElement.query(By.css('[data-testid="no-data-cta"]'));
      expect(cta).toBeNull();
    });

    it('34. should hide no-data-cta when recentUploads exist', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(
        of(makeUploadListResponse([makeUpload('x')])),
      );
      const fixture = createComponent();
      fixture.detectChanges();
      const cta = fixture.debugElement.query(By.css('[data-testid="no-data-cta"]'));
      expect(cta).toBeNull();
    });

    it('35. should show no-data-cta when all counts are zero and no uploads', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const cta = fixture.debugElement.query(By.css('[data-testid="no-data-cta"]'));
      expect(cta).not.toBeNull();
    });

    it('36. no-data-cta upload link navigates to /upload', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const link = fixture.debugElement.query(By.css('[data-testid="no-data-upload-link"]'));
      expect(link).not.toBeNull();
    });
  });

  // ── 6. Layout and styling elements ───────────────────────────────────────────

  describe('layout elements', () => {
    it('37. should show "Open" label next to open-count after successful counts load', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(4)))
        .mockReturnValueOnce(of(makePositionListResponse(2)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const countsCard = fixture.debugElement.query(By.css('[data-testid="counts-card"]'));
      expect(countsCard.nativeElement.textContent).toContain('Open');
    });

    it('38. should show "Closed" label next to closed-count after successful counts load', () => {
      pnlServiceMock.getSummary.mockReturnValue(of(makePnlSummary([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(4)))
        .mockReturnValueOnce(of(makePositionListResponse(2)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const countsCard = fixture.debugElement.query(By.css('[data-testid="counts-card"]'));
      expect(countsCard.nativeElement.textContent).toContain('Closed');
    });
  });
});
