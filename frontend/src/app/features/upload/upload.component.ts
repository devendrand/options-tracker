import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Output,
  inject,
  signal,
} from '@angular/core';
import { Upload } from '../../core/models/upload.model';
import { UploadService } from '../../core/services/upload.service';

@Component({
  selector: 'app-upload',
  templateUrl: './upload.component.html',
  styleUrl: './upload.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UploadComponent {
  private readonly uploadService = inject(UploadService);

  @Output() readonly uploaded = new EventEmitter<void>();

  private readonly _selectedFile = signal<File | null>(null);
  private readonly _isUploading = signal(false);
  private readonly _uploadResult = signal<Upload | null>(null);
  private readonly _errorMessage = signal<string | null>(null);

  get selectedFile(): File | null {
    return this._selectedFile();
  }

  set selectedFile(value: File | null) {
    this._selectedFile.set(value);
  }

  get isUploading(): boolean {
    return this._isUploading();
  }

  get uploadResult(): Upload | null {
    return this._uploadResult();
  }

  set uploadResult(value: Upload | null) {
    this._uploadResult.set(value);
  }

  get errorMessage(): string | null {
    return this._errorMessage();
  }

  set errorMessage(value: string | null) {
    this._errorMessage.set(value);
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    if (file) {
      this._selectedFile.set(file);
    }
  }

  upload(): void {
    const file = this._selectedFile();
    if (!file) {
      return;
    }
    this._isUploading.set(true);
    this._uploadResult.set(null);
    this._errorMessage.set(null);

    this.uploadService.createUpload(file).subscribe({
      next: (result) => {
        this._uploadResult.set(result);
        this._isUploading.set(false);
        this.uploaded.emit();
      },
      error: (err: { message?: string }) => {
        this._errorMessage.set(err?.message ?? 'An unexpected error occurred.');
        this._isUploading.set(false);
      },
    });
  }

  reset(): void {
    this._selectedFile.set(null);
    this._uploadResult.set(null);
    this._errorMessage.set(null);
    this._isUploading.set(false);
  }
}
