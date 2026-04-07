import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  ViewChild,
  computed,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { PositionService } from '@core/services/position.service';
import { UploadService } from '@core/services/upload.service';
import { Upload } from '@core/models/upload.model';
import { PnlSummaryComponent } from '@features/pnl-summary/pnl-summary.component';
import { UploadComponent } from '@features/upload/upload.component';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, PnlSummaryComponent, UploadComponent],
})
export class DashboardComponent implements OnInit {
  private readonly positionService = inject(PositionService);
  private readonly uploadService = inject(UploadService);

  @ViewChild(PnlSummaryComponent) pnlSummary?: PnlSummaryComponent;

  readonly countsLoading = signal<boolean>(false);
  readonly countsError = signal<string | null>(null);
  readonly openCount = signal<number>(0);
  readonly closedCount = signal<number>(0);

  readonly uploadsLoading = signal<boolean>(false);
  readonly uploadsError = signal<string | null>(null);
  readonly recentUploads = signal<Upload[]>([]);

  readonly hasData = computed(
    () => this.openCount() > 0 || this.closedCount() > 0 || this.recentUploads().length > 0,
  );

  ngOnInit(): void {
    this.loadCounts();
    this.loadRecentUploads();
  }

  loadCounts(): void {
    this.countsLoading.set(true);
    this.countsError.set(null);
    forkJoin({
      open: this.positionService.getPositions({ status: 'OPEN', limit: 1 }),
      closed: this.positionService.getPositions({ status: 'CLOSED', limit: 1 }),
    }).subscribe({
      next: ({ open, closed }) => {
        this.openCount.set(open.total);
        this.closedCount.set(closed.total);
        this.countsLoading.set(false);
      },
      error: (err: { message?: string }) => {
        this.countsError.set(err?.message ?? 'Failed to load position counts.');
        this.countsLoading.set(false);
      },
    });
  }

  loadRecentUploads(): void {
    this.uploadsLoading.set(true);
    this.uploadsError.set(null);
    this.uploadService.getUploads().subscribe({
      next: (response) => {
        this.recentUploads.set(response.items.slice(0, 5));
        this.uploadsLoading.set(false);
      },
      error: (err: { message?: string }) => {
        this.uploadsError.set(err?.message ?? 'Failed to load recent uploads.');
        this.uploadsLoading.set(false);
      },
    });
  }

  onUploadComplete(): void {
    this.loadRecentUploads();
    this.loadCounts();
    this.pnlSummary?.loadSummary();
  }
}
