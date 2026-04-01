import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { PnlService } from '@core/services/pnl.service';
import { PositionService } from '@core/services/position.service';
import { UploadService } from '@core/services/upload.service';
import { PnlSummary } from '@core/models/pnl.model';
import { Upload } from '@core/models/upload.model';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
})
export class DashboardComponent implements OnInit {
  private readonly pnlService = inject(PnlService);
  private readonly positionService = inject(PositionService);
  private readonly uploadService = inject(UploadService);

  readonly pnlLoading = signal<boolean>(false);
  readonly pnlError = signal<string | null>(null);
  readonly pnl = signal<PnlSummary | null>(null);

  readonly countsLoading = signal<boolean>(false);
  readonly countsError = signal<string | null>(null);
  readonly openCount = signal<number>(0);
  readonly closedCount = signal<number>(0);

  readonly uploadsLoading = signal<boolean>(false);
  readonly uploadsError = signal<string | null>(null);
  readonly recentUploads = signal<Upload[]>([]);

  readonly totalPnl = computed(() => {
    const summary = this.pnl();
    if (!summary || summary.items.length === 0) return '0.00';
    const sum = summary.items.reduce((acc, item) => acc + parseFloat(item.total_pnl), 0);
    return sum.toFixed(2);
  });

  readonly isPnlPositive = computed(() => parseFloat(this.totalPnl()) > 0);
  readonly isPnlNegative = computed(() => parseFloat(this.totalPnl()) < 0);

  readonly hasData = computed(
    () =>
      this.openCount() > 0 ||
      this.closedCount() > 0 ||
      this.recentUploads().length > 0,
  );

  ngOnInit(): void {
    this.loadPnl();
    this.loadCounts();
    this.loadRecentUploads();
  }

  loadPnl(): void {
    this.pnlLoading.set(true);
    this.pnlError.set(null);
    this.pnlService.getSummary({ period: 'year' }).subscribe({
      next: (summary) => {
        this.pnl.set(summary);
        this.pnlLoading.set(false);
      },
      error: (err: { message?: string }) => {
        this.pnlError.set(err?.message ?? 'Failed to load P&L summary.');
        this.pnlLoading.set(false);
      },
    });
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
}
