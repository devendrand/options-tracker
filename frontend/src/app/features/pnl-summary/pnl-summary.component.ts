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
  TimePeriodOption,
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
  readonly underlying = signal<string>('');
  readonly selectedTimePeriod = signal<string>('current-year');

  readonly expandedLabel = signal<string | null>(null);
  readonly bucketPositions = signal<PositionListResponse | null>(null);
  readonly bucketLoading = signal<boolean>(false);
  readonly bucketError = signal<string | null>(null);
  readonly expandedPositionIds = signal<Set<string>>(new Set());

  readonly totalPnl = computed(() => {
    const items = this.summary()?.items ?? [];
    return items.reduce((sum, e) => sum + parseFloat(e.total_pnl), 0).toFixed(2);
  });

  readonly timePeriodOptions = computed<TimePeriodOption[]>(() => {
    const now = new Date();
    const year = now.getFullYear();

    const fixed: TimePeriodOption[] = [
      {
        label: 'Last 7 Days',
        value: 'last-7',
        closed_after: this.daysAgo(7),
        closed_before: this.today(),
      },
      {
        label: 'Last 30 Days',
        value: 'last-30',
        closed_after: this.daysAgo(30),
        closed_before: this.today(),
      },
      {
        label: 'Last 60 Days',
        value: 'last-60',
        closed_after: this.daysAgo(60),
        closed_before: this.today(),
      },
      {
        label: 'Last 90 Days',
        value: 'last-90',
        closed_after: this.daysAgo(90),
        closed_before: this.today(),
      },
      {
        label: 'Current Year',
        value: 'current-year',
        closed_after: `${year}-01-01`,
        closed_before: `${year}-12-31`,
      },
      {
        label: 'Prior Year',
        value: 'prior-year',
        closed_after: `${year - 1}-01-01`,
        closed_before: `${year - 1}-12-31`,
      },
    ];

    return [...fixed, ...this.buildQuarterlyOptions(), { label: 'Custom', value: 'custom' }];
  });

  readonly selectedDates = computed(() => {
    const opt = this.timePeriodOptions().find((o) => o.value === this.selectedTimePeriod());
    return { closed_after: opt?.closed_after, closed_before: opt?.closed_before };
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

    const dates = this.selectedDates();
    const params: PnlQueryParams = {
      group_by: 'underlying',
    };
    if (this.underlying()) params.underlying = this.underlying();
    if (dates.closed_after) params.closed_after = dates.closed_after;
    if (dates.closed_before) params.closed_before = dates.closed_before;

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

  onUnderlyingChange(event: Event): void {
    this.underlying.set((event.target as HTMLInputElement).value);
    this.loadSummary();
  }

  onTimePeriodChange(event: Event): void {
    this.selectedTimePeriod.set((event.target as HTMLSelectElement).value);
    this.loadSummary();
  }

  pnlClass(value: string): string {
    const n = parseFloat(value);
    if (n > 0) return 'pnl-positive';
    if (n < 0) return 'pnl-negative';
    return '';
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
    const dates = this.selectedDates();
    const params: PnlPositionsParams = {
      period: 'year',
      group_by: 'underlying',
      period_label: label,
    };
    if (this.underlying()) params.underlying = this.underlying();
    if (dates.closed_after) params.closed_after = dates.closed_after;
    if (dates.closed_before) params.closed_before = dates.closed_before;
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

  daysHeld(pos: { opened_at: string | null; closed_at: string | null }): number | null {
    if (!pos.opened_at || !pos.closed_at) return null;
    const open = new Date(pos.opened_at + 'T00:00:00');
    const close = new Date(pos.closed_at + 'T00:00:00');
    return Math.round((close.getTime() - open.getTime()) / (1000 * 60 * 60 * 24));
  }

  daysToExpiry(expiry: string): number | null {
    if (!expiry) return null;
    const exp = new Date(expiry + 'T00:00:00');
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.ceil((exp.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  }

  isClosed(status: string): boolean {
    return ['CLOSED', 'EXPIRED', 'ASSIGNED', 'EXERCISED'].includes(status);
  }

  private today(): string {
    return new Date().toISOString().split('T')[0];
  }

  private daysAgo(n: number): string {
    const d = new Date();
    d.setDate(d.getDate() - n);
    return d.toISOString().split('T')[0];
  }

  private buildQuarterlyOptions(): TimePeriodOption[] {
    const now = new Date();
    const currentQ = Math.floor(now.getMonth() / 3);
    const currentYear = now.getFullYear();
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    const quarters: TimePeriodOption[] = [];
    for (let i = 0; i < 4; i++) {
      let q = currentQ - i;
      let y = currentYear;
      while (q < 0) {
        q += 4;
        y--;
      }
      const sm = q * 3;
      const em = sm + 2;
      const start = new Date(y, sm, 1);
      const end = new Date(y, em + 1, 0);
      quarters.push({
        label: `${months[sm]} - ${months[em]} ${y}`,
        value: `q${q}-${y}`,
        closed_after: start.toISOString().split('T')[0],
        closed_before: end.toISOString().split('T')[0],
      });
    }
    return quarters;
  }
}
