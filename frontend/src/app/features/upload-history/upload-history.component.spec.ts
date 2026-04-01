import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Subject, of, throwError } from 'rxjs';
import { DatePipe } from '@angular/common';
import { provideRouter } from '@angular/router';
import { UploadHistoryComponent } from './upload-history.component';
import { UploadService } from '@core/services/upload.service';
import { Upload, UploadListResponse } from '@core/models/upload.model';

function makeUpload(overrides: Partial<Upload> = {}): Upload {
  return {
    id: 'up-1',
    filename: 'trades.csv',
    status: 'ACTIVE',
    broker: 'ETRADE',
    row_count: 100,
    options_count: 20,
    duplicate_count: 2,
    possible_duplicate_count: 1,
    parse_error_count: 0,
    internal_transfer_count: 3,
    uploaded_at: '2026-03-15T10:00:00Z',
    ...overrides,
  };
}

function makeListResponse(items: Upload[] = [makeUpload()]): UploadListResponse {
  return { items, total: items.length, offset: 0, limit: 100 };
}

describe('UploadHistoryComponent', () => {
  let uploadServiceMock: jest.Mocked<Pick<UploadService, 'getUploads' | 'deleteUpload'>>;

  beforeEach(async () => {
    uploadServiceMock = {
      getUploads: jest.fn(),
      deleteUpload: jest.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [UploadHistoryComponent],
      providers: [
        { provide: UploadService, useValue: uploadServiceMock },
        DatePipe,
        provideRouter([]),
      ],
    }).compileComponents();
  });

  // ── 1. Initial state ──────────────────────────────────────────────────────────

  describe('initial state', () => {
    it('1. should create without error', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      expect(fixture.componentInstance).toBeTruthy();
    });

    it('2. should call getUploads on ngOnInit', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      expect(uploadServiceMock.getUploads).toHaveBeenCalledTimes(1);
    });

    it('3. should show loading state while request is in-flight', () => {
      const subject = new Subject<UploadListResponse>();
      uploadServiceMock.getUploads.mockReturnValue(subject.asObservable());
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="loading-state"]'))).not.toBeNull();
      subject.complete();
    });
  });

  // ── 2. Successful load ────────────────────────────────────────────────────────

  describe('successful load', () => {
    it('4. should render uploads table with correct row count', () => {
      const uploads = [makeUpload({ id: 'up-1' }), makeUpload({ id: 'up-2' })];
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse(uploads)));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      const rows = fixture.debugElement.queryAll(By.css('[data-testid^="upload-row-"]'));
      expect(rows.length).toBe(2);
    });

    it('5. should display filename, broker, and uploaded_at in first row', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid="upload-row-up-1"]'));
      const text = row.nativeElement.textContent;
      expect(text).toContain('trades.csv');
      expect(text).toContain('ETRADE');
      expect(text).toContain('Mar 15, 2026');
    });

    it('6. should render StatusBadgeComponent for the status column', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      const badge = fixture.debugElement.query(By.css('app-status-badge'));
      expect(badge).not.toBeNull();
    });

    it('7. should show empty state when getUploads returns []', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse([])));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="empty-state"]'))).not.toBeNull();
      expect(fixture.debugElement.query(By.css('[data-testid="uploads-table"]'))).toBeNull();
    });

    it('8. should render "—" when row_count is null', () => {
      uploadServiceMock.getUploads.mockReturnValue(
        of(makeListResponse([makeUpload({ row_count: null })])),
      );
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      const row = fixture.debugElement.query(By.css('[data-testid^="upload-row-"]'));
      expect(row.nativeElement.textContent).toContain('—');
    });
  });

  // ── 3. Error state ────────────────────────────────────────────────────────────

  describe('error state', () => {
    it('9. should show error state when API fails', () => {
      uploadServiceMock.getUploads.mockReturnValue(
        throwError(() => ({ message: 'Network error' })),
      );
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="error-state"]'))).not.toBeNull();
    });

    it('10. should display the error message', () => {
      uploadServiceMock.getUploads.mockReturnValue(throwError(() => ({ message: 'Server error' })));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      const err = fixture.debugElement.query(By.css('[data-testid="error-state"]'));
      expect(err.nativeElement.textContent).toContain('Server error');
    });

    it('11. should use fallback message when error has no message', () => {
      uploadServiceMock.getUploads.mockReturnValue(throwError(() => ({})));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      const err = fixture.debugElement.query(By.css('[data-testid="error-state"]'));
      expect(err.nativeElement.textContent).toContain('Failed to load uploads.');
    });

    it('12. should call loadUploads again when Retry is clicked', () => {
      uploadServiceMock.getUploads.mockReturnValue(throwError(() => ({ message: 'err' })));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      uploadServiceMock.getUploads.mockClear();
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      fixture.debugElement.query(By.css('[data-testid="retry-btn"]')).nativeElement.click();
      expect(uploadServiceMock.getUploads).toHaveBeenCalledTimes(1);
    });
  });

  // ── 4. Delete flow ────────────────────────────────────────────────────────────

  describe('delete flow', () => {
    it('13. should render a Delete button for each row', () => {
      const uploads = [makeUpload({ id: 'up-1' }), makeUpload({ id: 'up-2' })];
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse(uploads)));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      expect(fixture.debugElement.query(By.css('[data-testid="delete-btn-up-1"]'))).not.toBeNull();
      expect(fixture.debugElement.query(By.css('[data-testid="delete-btn-up-2"]'))).not.toBeNull();
    });

    it('14. should show confirmation dialog when Delete is clicked', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.detectChanges();

      expect(
        fixture.debugElement.query(By.css('[data-testid="delete-confirm-dialog"]')),
      ).not.toBeNull();
    });

    it('15. should show duplicate-resurfacing warning in confirmation dialog', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.detectChanges();

      const warning = fixture.debugElement.query(By.css('[data-testid="delete-warning-text"]'));
      expect(warning.nativeElement.textContent).toContain('POSSIBLE_DUPLICATE');
    });

    it('16. should hide confirmation dialog when Cancel is clicked', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.detectChanges();
      fixture.componentInstance.cancelDelete();
      fixture.detectChanges();

      expect(
        fixture.debugElement.query(By.css('[data-testid="delete-confirm-dialog"]')),
      ).toBeNull();
    });

    it('17. should not call deleteUpload when Cancel is clicked', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.detectChanges();
      fixture.componentInstance.cancelDelete();

      expect(uploadServiceMock.deleteUpload).not.toHaveBeenCalled();
    });

    it('18. should call deleteUpload with correct id when Confirm Delete is clicked', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      uploadServiceMock.deleteUpload.mockReturnValue(of(undefined));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.detectChanges();
      fixture.componentInstance.executeDelete();

      expect(uploadServiceMock.deleteUpload).toHaveBeenCalledWith('up-1');
    });

    it('19. should remove the deleted row from the table after successful delete', () => {
      const uploads = [makeUpload({ id: 'up-1' }), makeUpload({ id: 'up-2' })];
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse(uploads)));
      uploadServiceMock.deleteUpload.mockReturnValue(of(undefined));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.componentInstance.executeDelete();
      fixture.detectChanges();

      expect(fixture.debugElement.query(By.css('[data-testid="upload-row-up-1"]'))).toBeNull();
      expect(fixture.debugElement.query(By.css('[data-testid="upload-row-up-2"]'))).not.toBeNull();
    });

    it('20. should clear deletingId after successful delete', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      uploadServiceMock.deleteUpload.mockReturnValue(of(undefined));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.componentInstance.executeDelete();

      expect(fixture.componentInstance.deletingId()).toBeNull();
    });

    it('21. should show delete error when deleteUpload fails', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      uploadServiceMock.deleteUpload.mockReturnValue(
        throwError(() => ({ message: 'Delete failed' })),
      );
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.detectChanges();
      fixture.componentInstance.executeDelete();
      fixture.detectChanges();

      const errEl = fixture.debugElement.query(By.css('[data-testid="delete-error-text"]'));
      expect(errEl).not.toBeNull();
      expect(errEl.nativeElement.textContent).toContain('Delete failed');
    });

    it('22. should use fallback delete error message when error has no message', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      uploadServiceMock.deleteUpload.mockReturnValue(throwError(() => ({})));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.componentInstance.executeDelete();

      expect(fixture.componentInstance.deleteError()).toBe('Failed to delete upload.');
    });

    it('23. should keep confirmation dialog open after a delete error', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      uploadServiceMock.deleteUpload.mockReturnValue(throwError(() => ({ message: 'err' })));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.detectChanges();
      fixture.componentInstance.executeDelete();
      fixture.detectChanges();

      expect(
        fixture.debugElement.query(By.css('[data-testid="delete-confirm-dialog"]')),
      ).not.toBeNull();
    });

    it('24. opening a second confirmation closes the first (one panel at a time)', () => {
      const uploads = [makeUpload({ id: 'up-1' }), makeUpload({ id: 'up-2' })];
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse(uploads)));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.confirmDelete('up-1');
      fixture.detectChanges();
      fixture.componentInstance.confirmDelete('up-2');
      fixture.detectChanges();

      expect(
        fixture.debugElement.query(By.css('[data-confirm-id="confirm-panel-up-1"]')),
      ).toBeNull();
      expect(
        fixture.debugElement.query(By.css('[data-confirm-id="confirm-panel-up-2"]')),
      ).not.toBeNull();
    });

    it('25. should do nothing if executeDelete is called when deletingId is null', () => {
      uploadServiceMock.getUploads.mockReturnValue(of(makeListResponse()));
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();

      fixture.componentInstance.executeDelete();
      expect(uploadServiceMock.deleteUpload).not.toHaveBeenCalled();
    });
  });

  // ── 5. POSSIBLE_DUPLICATE link ────────────────────────────────────────────────

  describe('possible duplicate link', () => {
    it('26. should render POSSIBLE_DUPLICATE count as a link when count > 0', () => {
      uploadServiceMock.getUploads.mockReturnValue(
        of(makeListResponse([makeUpload({ id: 'up-1', possible_duplicate_count: 3 })])),
      );
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      expect(
        fixture.debugElement.query(By.css('[data-testid="possible-duplicate-link"]')),
      ).not.toBeNull();
    });

    it('27. should not render POSSIBLE_DUPLICATE as a link when count is 0', () => {
      uploadServiceMock.getUploads.mockReturnValue(
        of(makeListResponse([makeUpload({ id: 'up-1', possible_duplicate_count: 0 })])),
      );
      const fixture = TestBed.createComponent(UploadHistoryComponent);
      fixture.detectChanges();
      expect(
        fixture.debugElement.query(By.css('[data-testid="possible-duplicate-link"]')),
      ).toBeNull();
    });
  });
});
