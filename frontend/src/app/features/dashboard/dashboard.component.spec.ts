import { Component, EventEmitter, Output } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Subject, of, throwError } from 'rxjs';
import { provideRouter } from '@angular/router';
import { DashboardComponent } from './dashboard.component';
import { PnlSummaryComponent } from '@features/pnl-summary/pnl-summary.component';
import { UploadComponent } from '@features/upload/upload.component';
import { PositionService } from '@core/services/position.service';
import { UploadService } from '@core/services/upload.service';
import { Upload, UploadListResponse } from '@core/models/upload.model';
import { PositionListResponse } from '@core/models/position.model';

@Component({ selector: 'app-pnl-summary', template: '', standalone: true })
class MockPnlSummaryComponent {
  loadSummary = jest.fn();
}

@Component({ selector: 'app-upload', template: '', standalone: true })
class MockUploadComponent {
  @Output() readonly uploaded = new EventEmitter<void>();
}

function makePositionListResponse(total: number): PositionListResponse {
  return { total, offset: 0, limit: 1, options_items: [], equity_items: [] };
}

function makeUpload(id: string, filename = `upload-${id}.csv`): Upload {
  return {
    id,
    filename,
    status: 'ACTIVE',
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
  let positionServiceMock: jest.Mocked<Pick<PositionService, 'getPositions'>>;
  let uploadServiceMock: jest.Mocked<Pick<UploadService, 'getUploads'>>;

  function setupDefaultMocks() {
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
    positionServiceMock = { getPositions: jest.fn() };
    uploadServiceMock = { getUploads: jest.fn() };

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        { provide: PositionService, useValue: positionServiceMock },
        { provide: UploadService, useValue: uploadServiceMock },
        provideRouter([]),
      ],
    })
      .overrideComponent(DashboardComponent, {
        remove: { imports: [PnlSummaryComponent, UploadComponent] },
        add: { imports: [MockPnlSummaryComponent, MockUploadComponent] },
      })
      .compileComponents();
  });

  // ── 1. Initialisation ─────────────────────────────────────────────────────

  describe('initialisation', () => {
    it('1. should create without error', () => {
      setupDefaultMocks();
      const fixture = createComponent();
      fixture.detectChanges();
      expect(fixture.componentInstance).toBeTruthy();
    });

    it('2. should call getPositions (x2) and getUploads on init', () => {
      setupDefaultMocks();
      const fixture = createComponent();
      fixture.detectChanges();
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
      const openSubject = new Subject<PositionListResponse>();
      const closedSubject = new Subject<PositionListResponse>();
      const uploadsSubject = new Subject<UploadListResponse>();
      positionServiceMock.getPositions
        .mockReturnValueOnce(openSubject.asObservable())
        .mockReturnValueOnce(closedSubject.asObservable());
      uploadServiceMock.getUploads.mockReturnValue(uploadsSubject.asObservable());
      const fixture = createComponent();
      fixture.detectChanges();
      const cta = fixture.debugElement.query(By.css('[data-testid="no-data-cta"]'));
      expect(cta).not.toBeNull();
      openSubject.complete();
      closedSubject.complete();
      uploadsSubject.complete();
    });

    it('4. should render the app-pnl-summary element', () => {
      setupDefaultMocks();
      const fixture = createComponent();
      fixture.detectChanges();
      const pnlSection = fixture.debugElement.query(By.css('[data-testid="pnl-summary-section"]'));
      expect(pnlSection).not.toBeNull();
    });
  });

  // ── 2. Counts section ─────────────────────────────────────────────────────

  describe('counts section', () => {
    it('5. should show counts-loading while request is in-flight', () => {
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

    it('6. should not show open-count while counts are loading', () => {
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

    it('7. should show open-count after successful counts load', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(7)))
        .mockReturnValueOnce(of(makePositionListResponse(3)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const openCount = fixture.debugElement.query(By.css('[data-testid="open-count"]'));
      expect(openCount.nativeElement.textContent.trim()).toBe('7');
    });

    it('8. should show closed-count after successful counts load', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(7)))
        .mockReturnValueOnce(of(makePositionListResponse(3)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const closedCount = fixture.debugElement.query(By.css('[data-testid="closed-count"]'));
      expect(closedCount.nativeElement.textContent.trim()).toBe('3');
    });

    it('9. should show counts-error when getPositions fails', () => {
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

    it('10. should use fallback counts-error message when error has no message', () => {
      positionServiceMock.getPositions.mockReturnValue(throwError(() => ({})));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const errEl = fixture.debugElement.query(By.css('[data-testid="counts-error"]'));
      expect(errEl.nativeElement.textContent).toContain('Failed to load position counts.');
    });

    it('11. should call loadCounts again when counts retry button is clicked', () => {
      positionServiceMock.getPositions.mockReturnValue(throwError(() => ({ message: 'error' })));
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

    it('12. should clear counts-loading after an error', () => {
      positionServiceMock.getPositions.mockReturnValue(throwError(() => ({ message: 'error' })));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="counts-loading"]'));
      expect(loading).toBeNull();
    });
  });

  // ── 3. Uploads section ────────────────────────────────────────────────────

  describe('uploads section', () => {
    it('13. should show uploads-loading while request is in-flight', () => {
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

    it('14. should show uploads-empty when no uploads exist', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const empty = fixture.debugElement.query(By.css('[data-testid="uploads-empty"]'));
      expect(empty).not.toBeNull();
    });

    it('15. should show upload links when uploads exist', () => {
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

    it('16. should limit upload links to 5', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      const manyUploads = ['1', '2', '3', '4', '5', '6', '7'].map(makeUpload);
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse(manyUploads)));
      const fixture = createComponent();
      fixture.detectChanges();
      const links = fixture.debugElement.queryAll(By.css('[data-testid^="upload-link-"]'));
      expect(links.length).toBe(5);
    });

    it('17. should show uploads-error when getUploads fails', () => {
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

    it('18. should use fallback uploads-error message when error has no message', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(throwError(() => ({})));
      const fixture = createComponent();
      fixture.detectChanges();
      const errEl = fixture.debugElement.query(By.css('[data-testid="uploads-error"]'));
      expect(errEl.nativeElement.textContent).toContain('Failed to load recent uploads.');
    });

    it('19. should call loadRecentUploads again when uploads retry button is clicked', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(throwError(() => ({ message: 'error' })));
      const fixture = createComponent();
      fixture.detectChanges();

      uploadServiceMock.getUploads.mockClear();
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));

      const retryBtn = fixture.debugElement.query(By.css('[data-testid="uploads-retry-btn"]'));
      retryBtn.nativeElement.click();
      expect(uploadServiceMock.getUploads).toHaveBeenCalledTimes(1);
    });

    it('20. should clear uploads-loading after an error', () => {
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

  // ── 4. hasData / no-data-cta ──────────────────────────────────────────────

  describe('hasData and no-data-cta', () => {
    it('21. should hide no-data-cta when openCount > 0', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(3)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const cta = fixture.debugElement.query(By.css('[data-testid="no-data-cta"]'));
      expect(cta).toBeNull();
    });

    it('22. should hide no-data-cta when closedCount > 0', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(8)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const cta = fixture.debugElement.query(By.css('[data-testid="no-data-cta"]'));
      expect(cta).toBeNull();
    });

    it('23. should hide no-data-cta when recentUploads exist', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([makeUpload('x')])));
      const fixture = createComponent();
      fixture.detectChanges();
      const cta = fixture.debugElement.query(By.css('[data-testid="no-data-cta"]'));
      expect(cta).toBeNull();
    });

    it('24. should show no-data-cta when all counts are zero and no uploads', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const cta = fixture.debugElement.query(By.css('[data-testid="no-data-cta"]'));
      expect(cta).not.toBeNull();
    });

    it('25. no-data-cta upload link is rendered', () => {
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

  // ── 5. Layout and styling elements ────────────────────────────────────────

  describe('layout elements', () => {
    it('26. should show "Open" label next to open-count after successful counts load', () => {
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(4)))
        .mockReturnValueOnce(of(makePositionListResponse(2)));
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      const fixture = createComponent();
      fixture.detectChanges();
      const countsCard = fixture.debugElement.query(By.css('[data-testid="counts-card"]'));
      expect(countsCard.nativeElement.textContent).toContain('Open');
    });

    it('27. should show "Closed" label next to closed-count after successful counts load', () => {
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

  // ── 6. Embedded upload component ─────────────────────────────────────────

  describe('embedded upload', () => {
    it('28. should render app-upload element inside uploads card', () => {
      setupDefaultMocks();
      const fixture = createComponent();
      fixture.detectChanges();
      const uploadsCard = fixture.debugElement.query(By.css('[data-testid="uploads-card"]'));
      const embeddedUpload = uploadsCard.query(By.css('[data-testid="embedded-upload"]'));
      expect(embeddedUpload).not.toBeNull();
    });

    it('29. onUploadComplete calls loadRecentUploads and loadCounts', () => {
      setupDefaultMocks();
      const fixture = createComponent();
      fixture.detectChanges();

      uploadServiceMock.getUploads.mockClear();
      positionServiceMock.getPositions.mockClear();
      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));

      fixture.componentInstance.onUploadComplete();

      expect(uploadServiceMock.getUploads).toHaveBeenCalledTimes(1);
      expect(positionServiceMock.getPositions).toHaveBeenCalledTimes(2);
    });

    it('30. onUploadComplete calls pnlSummary.loadSummary when ViewChild is available', () => {
      setupDefaultMocks();
      const fixture = createComponent();
      fixture.detectChanges();

      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));

      const mockPnlSummary = { loadSummary: jest.fn() };
      fixture.componentInstance.pnlSummary = mockPnlSummary as unknown as PnlSummaryComponent;

      fixture.componentInstance.onUploadComplete();

      expect(mockPnlSummary.loadSummary).toHaveBeenCalledTimes(1);
    });

    it('31. onUploadComplete does not throw when pnlSummary ViewChild is undefined', () => {
      setupDefaultMocks();
      const fixture = createComponent();
      fixture.detectChanges();

      uploadServiceMock.getUploads.mockReturnValue(of(makeUploadListResponse([])));
      positionServiceMock.getPositions
        .mockReturnValueOnce(of(makePositionListResponse(0)))
        .mockReturnValueOnce(of(makePositionListResponse(0)));

      fixture.componentInstance.pnlSummary = undefined;

      expect(() => fixture.componentInstance.onUploadComplete()).not.toThrow();
    });
  });
});
