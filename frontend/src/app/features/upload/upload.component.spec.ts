import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Subject, of, throwError } from 'rxjs';
import { UploadComponent } from './upload.component';
import { UploadService } from '../../core/services/upload.service';
import { Upload } from '../../core/models/upload.model';

const mockUpload: Upload = {
  id: 'abc123',
  filename: 'trades.csv',
  status: 'ACTIVE',
  broker: 'ETRADE',
  row_count: 42,
  options_count: 10,
  duplicate_count: 2,
  possible_duplicate_count: 1,
  parse_error_count: 1,
  internal_transfer_count: 0,
  uploaded_at: '2026-03-15T10:00:00Z',
};

function makeFile(name = 'trades.csv'): File {
  return new File(['col1,col2\nval1,val2'], name, { type: 'text/csv' });
}

describe('UploadComponent', () => {
  let uploadServiceMock: jest.Mocked<Pick<UploadService, 'createUpload'>>;

  beforeEach(async () => {
    uploadServiceMock = {
      createUpload: jest.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [UploadComponent],
      providers: [{ provide: UploadService, useValue: uploadServiceMock }],
    }).compileComponents();
  });

  // ── 1. Initial state ────────────────────────────────────────────────────────

  describe('initial state', () => {
    it('should create', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      expect(fixture.componentInstance).toBeTruthy();
    });

    it('should have no file selected initially', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      expect(fixture.componentInstance.selectedFile).toBeNull();
    });

    it('should have upload button disabled when no file is selected', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();
      const button: HTMLButtonElement = fixture.debugElement.query(
        By.css('[data-testid="upload-btn"]'),
      ).nativeElement;
      expect(button.disabled).toBe(true);
    });

    it('should not show loading state initially', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();
      const loading = fixture.debugElement.query(By.css('[data-testid="loading-state"]'));
      expect(loading).toBeNull();
    });

    it('should not show result state initially', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();
      const result = fixture.debugElement.query(By.css('[data-testid="result-state"]'));
      expect(result).toBeNull();
    });

    it('should not show error state initially', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();
      const error = fixture.debugElement.query(By.css('[data-testid="error-state"]'));
      expect(error).toBeNull();
    });

    it('should render a file input that accepts only .csv files', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();
      const input: HTMLInputElement = fixture.debugElement.query(
        By.css('input[type="file"]'),
      ).nativeElement;
      expect(input.accept).toBe('.csv');
    });
  });

  // ── 2. File selection via input ─────────────────────────────────────────────

  describe('file selection via input', () => {
    it('should set selectedFile when a file is chosen via input', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();
      const file = makeFile();
      const input: HTMLInputElement = fixture.debugElement.query(
        By.css('input[type="file"]'),
      ).nativeElement;

      Object.defineProperty(input, 'files', { value: [file], configurable: true });
      const event = new Event('change');
      input.dispatchEvent(event);
      fixture.detectChanges();

      expect(fixture.componentInstance.selectedFile).toBe(file);
    });

    it('should enable upload button after file is selected', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();
      const file = makeFile();
      const input: HTMLInputElement = fixture.debugElement.query(
        By.css('input[type="file"]'),
      ).nativeElement;

      Object.defineProperty(input, 'files', { value: [file], configurable: true });
      input.dispatchEvent(new Event('change'));
      fixture.detectChanges();

      const button: HTMLButtonElement = fixture.debugElement.query(
        By.css('[data-testid="upload-btn"]'),
      ).nativeElement;
      expect(button.disabled).toBe(false);
    });

    it('should not set selectedFile when no files in event', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();
      const input: HTMLInputElement = fixture.debugElement.query(
        By.css('input[type="file"]'),
      ).nativeElement;

      Object.defineProperty(input, 'files', { value: [], configurable: true });
      input.dispatchEvent(new Event('change'));
      fixture.detectChanges();

      expect(fixture.componentInstance.selectedFile).toBeNull();
    });
  });

  // ── 3. Drag and drop ────────────────────────────────────────────────────────

  describe('drag and drop', () => {
    it('should set selectedFile from dropped file', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();
      const file = makeFile();

      const mockEvent = {
        preventDefault: jest.fn(),
        dataTransfer: { files: [file] },
      } as unknown as DragEvent;

      fixture.componentInstance.onDrop(mockEvent);
      fixture.detectChanges();

      expect(fixture.componentInstance.selectedFile).toBe(file);
    });

    it('should not set selectedFile if drop has no files', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();

      const mockEvent = {
        preventDefault: jest.fn(),
        dataTransfer: { files: [] },
      } as unknown as DragEvent;

      fixture.componentInstance.onDrop(mockEvent);
      fixture.detectChanges();

      expect(fixture.componentInstance.selectedFile).toBeNull();
    });

    it('should not set selectedFile if dataTransfer is null', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();

      const mockEvent = {
        preventDefault: jest.fn(),
        dataTransfer: null,
      } as unknown as DragEvent;

      fixture.componentInstance.onDrop(mockEvent);
      fixture.detectChanges();

      expect(fixture.componentInstance.selectedFile).toBeNull();
    });

    it('should prevent default on dragover', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();

      const mockEvent = {
        preventDefault: jest.fn(),
      } as unknown as DragEvent;

      fixture.componentInstance.onDragOver(mockEvent);

      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });

    it('should render upload zone with drop and dragover bindings', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.detectChanges();
      const zone = fixture.debugElement.query(By.css('[data-testid="upload-zone"]'));
      expect(zone).not.toBeNull();
    });
  });

  // ── 4. Upload success ───────────────────────────────────────────────────────

  describe('upload success', () => {
    it('should have isUploading as false before uploading', () => {
      uploadServiceMock.createUpload.mockReturnValue(of(mockUpload));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      expect(fixture.componentInstance.isUploading).toBe(false);
    });

    it('should display loading state while uploading', () => {
      const subject = new Subject<Upload>();
      uploadServiceMock.createUpload.mockReturnValue(subject.asObservable());

      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      const loading = fixture.debugElement.query(By.css('[data-testid="loading-state"]'));
      expect(loading).not.toBeNull();
      expect(loading.nativeElement.textContent).toContain('Uploading');

      subject.complete();
    });

    it('should set uploadResult and clear isUploading on success', () => {
      uploadServiceMock.createUpload.mockReturnValue(of(mockUpload));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      expect(fixture.componentInstance.uploadResult).toEqual(mockUpload);
      expect(fixture.componentInstance.isUploading).toBe(false);
    });

    it('should display upload result with filename', () => {
      uploadServiceMock.createUpload.mockReturnValue(of(mockUpload));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      const result = fixture.debugElement.query(By.css('[data-testid="result-state"]'));
      expect(result).not.toBeNull();
      expect(result.nativeElement.textContent).toContain('trades.csv');
    });

    it('should display row_count in result', () => {
      uploadServiceMock.createUpload.mockReturnValue(of(mockUpload));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      const result = fixture.debugElement.query(By.css('[data-testid="result-state"]'));
      expect(result.nativeElement.textContent).toContain('42');
    });

    it('should display options_count in result', () => {
      uploadServiceMock.createUpload.mockReturnValue(of(mockUpload));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      const result = fixture.debugElement.query(By.css('[data-testid="result-state"]'));
      expect(result.nativeElement.textContent).toContain('10');
    });

    it('should display duplicate_count in result', () => {
      uploadServiceMock.createUpload.mockReturnValue(of(mockUpload));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      const result = fixture.debugElement.query(By.css('[data-testid="result-state"]'));
      expect(result.nativeElement.textContent).toContain('2');
    });

    it('should display parse_error_count in result', () => {
      uploadServiceMock.createUpload.mockReturnValue(of(mockUpload));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      const result = fixture.debugElement.query(By.css('[data-testid="result-state"]'));
      expect(result.nativeElement.textContent).toContain('1');
    });

    it('should show "Upload Another" button in result state', () => {
      uploadServiceMock.createUpload.mockReturnValue(of(mockUpload));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      const btn = fixture.debugElement.query(By.css('[data-testid="upload-another-btn"]'));
      expect(btn).not.toBeNull();
    });
  });

  // ── 5. Upload error ─────────────────────────────────────────────────────────

  describe('upload error', () => {
    it('should set errorMessage and clear isUploading on HTTP error', () => {
      uploadServiceMock.createUpload.mockReturnValue(
        throwError(() => ({ message: 'Upload failed' })),
      );
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      expect(fixture.componentInstance.errorMessage).toBe('Upload failed');
      expect(fixture.componentInstance.isUploading).toBe(false);
    });

    it('should display error message in template', () => {
      uploadServiceMock.createUpload.mockReturnValue(
        throwError(() => ({ message: 'Network error' })),
      );
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      const errorEl = fixture.debugElement.query(By.css('[data-testid="error-state"]'));
      expect(errorEl).not.toBeNull();
      expect(errorEl.nativeElement.textContent).toContain('Network error');
    });

    it('should show "Try Again" button in error state', () => {
      uploadServiceMock.createUpload.mockReturnValue(
        throwError(() => ({ message: 'Server error' })),
      );
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      const btn = fixture.debugElement.query(By.css('[data-testid="try-again-btn"]'));
      expect(btn).not.toBeNull();
    });

    it('should use a fallback message when error has no message property', () => {
      uploadServiceMock.createUpload.mockReturnValue(throwError(() => ({})));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      expect(fixture.componentInstance.errorMessage).toBe('An unexpected error occurred.');
    });
  });

  // ── 6. Reset ─────────────────────────────────────────────────────────────────

  describe('reset()', () => {
    it('should clear selectedFile, uploadResult, and errorMessage', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      const comp = fixture.componentInstance;
      comp.selectedFile = makeFile();
      comp.uploadResult = mockUpload;
      comp.errorMessage = 'some error';

      comp.reset();

      expect(comp.selectedFile).toBeNull();
      expect(comp.uploadResult).toBeNull();
      expect(comp.errorMessage).toBeNull();
    });

    it('should return to upload zone after reset from result state', () => {
      uploadServiceMock.createUpload.mockReturnValue(of(mockUpload));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      fixture.componentInstance.reset();
      fixture.detectChanges();

      const zone = fixture.debugElement.query(By.css('[data-testid="upload-zone"]'));
      expect(zone).not.toBeNull();
    });

    it('should return to upload zone after reset from error state', () => {
      uploadServiceMock.createUpload.mockReturnValue(throwError(() => ({ message: 'fail' })));
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = makeFile();
      fixture.detectChanges();

      fixture.componentInstance.upload();
      fixture.detectChanges();

      fixture.componentInstance.reset();
      fixture.detectChanges();

      const zone = fixture.debugElement.query(By.css('[data-testid="upload-zone"]'));
      expect(zone).not.toBeNull();
    });
  });

  // ── 7. Guard: upload() no-ops when no file ──────────────────────────────────

  describe('upload() with no file', () => {
    it('should not call uploadService.createUpload when selectedFile is null', () => {
      const fixture = TestBed.createComponent(UploadComponent);
      fixture.componentInstance.selectedFile = null;
      fixture.detectChanges();

      fixture.componentInstance.upload();

      expect(uploadServiceMock.createUpload).not.toHaveBeenCalled();
    });
  });
});
