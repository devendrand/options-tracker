import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import {
  PnlGroupBy,
  PnlPeriod,
  PnlPositionsParams,
  PnlQueryParams,
  PnlSummary,
} from '@core/models/pnl.model';
import { PositionListResponse } from '@core/models/position.model';
import { PnlService } from '@core/services/pnl.service';
import { PositionDrawerComponent } from '@features/positions/position-drawer/position-drawer.component';
import { StatusBadgeComponent } from '@shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-pnl-summary',
  templateUrl: './pnl-summary.component.html',
  styleUrl: './pnl-summary.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [PositionDrawerComponent, StatusBadgeComponent, DatePipe],
})
export class PnlSummaryComponent implements OnInit {
  private readonly pnlService = inject(PnlService);

  readonly loading = signal<boolean>(false);
  readonly error = signal<string | null>(null);
  readonly summary = signal<PnlSummary | null>(null);
  readonly period = signal<PnlPeriod>('year');
  readonly underlying = signal<string>('');
  readonly groupBy = signal<PnlGroupBy>('period');

  readonly expandedLabel = signal<string | null>(null);
  readonly bucketPositions = signal<PositionListResponse | null>(null);
  readonly bucketLoading = signal<boolean>(false);
  readonly bucketError = signal<string | null>(null);
  readonly expandedPositionIds = signal<Set<string>>(new Set());

  readonly totalPnl = computed(() => {
    const items = this.summary()?.items ?? [];
    return items.reduce((sum, e) => sum + parseFloat(e.total_pnl), 0).toFixed(2);
  });

  readonly periodDisabled = computed(() => this.groupBy() === 'underlying');

  readonly firstColumnHeader = computed(() => {
    return this.groupBy() === 'underlying' ? 'Underlying' : 'Period';
  });

  ngOnInit(): void {
    this.loadSummary();
  }

  loadSummary(): void {
    this.expandedLabel.set(null);
    this.bucketPositions.set(null);
    this.expandedPositionIds.set(new Set());

    this.loading.set(true);
    this.error.set(null);

    const params: PnlQueryParams = {
      period: this.period(),
      group_by: this.groupBy(),
    };
    if (this.underlying()) params.underlying = this.underlying();

    this.pnlService.getSummary(params).subscribe({
      next: (summary) => {
        this.summary.set(summary);
        this.loading.set(false);
      },
      error: (err: { message?: string }) => {
        this.error.set(err?.message ?? 'Failed to load P&L summary.');
        this.loading.set(false);
      },
    });
  }

  setPeriod(p: PnlPeriod): void {
    this.period.set(p);
    this.loadSummary();
  }

  setGroupBy(g: PnlGroupBy): void {
    this.groupBy.set(g);
    this.loadSummary();
  }

  onUnderlyingChange(event: Event): void {
    this.underlying.set((event.target as HTMLInputElement).value);
    this.loadSummary();
  }

  pnlClass(value: string): string {
    const n = parseFloat(value);
    if (n > 0) return 'pnl-positive';
    if (n < 0) return 'pnl-negative';
    return '';
  }

  formatPeriodLabel(label: string, p: PnlPeriod, groupBy?: PnlGroupBy): string {
    if (groupBy === 'underlying') {
      return label;
    }
    if (p === 'month') {
      const [year, month] = label.split('-');
      const date = new Date(Number(year), Number(month) - 1, 1);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        year: 'numeric',
        timeZone: 'UTC',
      });
    }
    return label;
  }

  toggleCard(label: string): void {
    if (this.expandedLabel() === label) {
      this.expandedLabel.set(null);
      this.bucketPositions.set(null);
      this.expandedPositionIds.set(new Set());
      return;
    }
    this.expandedLabel.set(label);
    this.expandedPositionIds.set(new Set());
    this.loadBucketPositions(label);
  }

  loadBucketPositions(label: string): void {
    this.bucketLoading.set(true);
    this.bucketError.set(null);
    this.bucketPositions.set(null);
    const params: PnlPositionsParams = {
      period: this.period(),
      group_by: this.groupBy(),
      period_label: label,
    };
    if (this.underlying()) params.underlying = this.underlying();
    this.pnlService.getPositionsForBucket(params).subscribe({
      next: (response) => {
        this.bucketPositions.set(response);
        this.bucketLoading.set(false);
      },
      error: (err: { message?: string }) => {
        this.bucketError.set(err?.message ?? 'Failed to load positions.');
        this.bucketLoading.set(false);
      },
    });
  }

  togglePositionDrawer(id: string): void {
    const current = new Set(this.expandedPositionIds());
    if (current.has(id)) {
      current.delete(id);
    } else {
      current.add(id);
    }
    this.expandedPositionIds.set(current);
  }

  isPositionExpanded(id: string): boolean {
    return this.expandedPositionIds().has(id);
  }
}
