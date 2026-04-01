import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { PnlPeriod, PnlQueryParams, PnlSummary } from '@core/models/pnl.model';
import { PnlService } from '@core/services/pnl.service';

@Component({
  selector: 'app-pnl-summary',
  templateUrl: './pnl-summary.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [],
})
export class PnlSummaryComponent implements OnInit {
  private readonly pnlService = inject(PnlService);

  readonly loading = signal<boolean>(false);
  readonly error = signal<string | null>(null);
  readonly summary = signal<PnlSummary | null>(null);
  readonly period = signal<PnlPeriod>('year');
  readonly underlying = signal<string>('');

  readonly totalPnl = computed(() => {
    const items = this.summary()?.items ?? [];
    return items.reduce((sum, e) => sum + parseFloat(e.total_pnl), 0).toFixed(2);
  });

  ngOnInit(): void {
    this.loadSummary();
  }

  loadSummary(): void {
    this.loading.set(true);
    this.error.set(null);

    const params: PnlQueryParams = { period: this.period() };
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

  formatPeriodLabel(label: string, p: PnlPeriod): string {
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
}
