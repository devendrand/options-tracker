import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Upload, UploadListResponse } from '@core/models/upload.model';
import { UploadService } from '@core/services/upload.service';
import { RelativeDatePipe } from '@shared/pipes/relative-date.pipe';
import { StatusBadgeComponent } from '@shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-upload-history',
  templateUrl: './upload-history.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, RelativeDatePipe, StatusBadgeComponent],
})
export class UploadHistoryComponent implements OnInit {
  private readonly uploadService = inject(UploadService);

  readonly loading = signal<boolean>(false);
  readonly error = signal<string | null>(null);
  readonly uploads = signal<Upload[]>([]);
  readonly deletingId = signal<string | null>(null);
  readonly deleteError = signal<string | null>(null);

  ngOnInit(): void {
    this.loadUploads();
  }

  loadUploads(): void {
    this.loading.set(true);
    this.error.set(null);
    this.uploadService.getUploads().subscribe({
      next: (response: UploadListResponse) => {
        this.uploads.set(response.items);
        this.loading.set(false);
      },
      error: (err: { message?: string }) => {
        this.error.set(err?.message ?? 'Failed to load uploads.');
        this.loading.set(false);
      },
    });
  }

  confirmDelete(id: string): void {
    this.deletingId.set(id);
    this.deleteError.set(null);
  }

  cancelDelete(): void {
    this.deletingId.set(null);
    this.deleteError.set(null);
  }

  executeDelete(): void {
    const id = this.deletingId();
    if (!id) return;
    this.uploadService.deleteUpload(id).subscribe({
      next: () => {
        this.uploads.set(this.uploads().filter((u) => u.id !== id));
        this.deletingId.set(null);
        this.deleteError.set(null);
      },
      error: (err: { message?: string }) => {
        this.deleteError.set(err?.message ?? 'Failed to delete upload.');
      },
    });
  }
}
