import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import {
  OptionsPosition,
  OptionsPositionStatus,
  PositionQueryParams,
} from '@core/models/position.model';
import { PositionService } from '@core/services/position.service';
import { StatusBadgeComponent } from '@shared/components/status-badge/status-badge.component';
import { PositionDrawerComponent } from './position-drawer/position-drawer.component';

export const POSITION_STATUSES: OptionsPositionStatus[] = [
  'OPEN',
  'PARTIALLY_CLOSED',
  'CLOSED',
  'EXPIRED',
  'ASSIGNED',
  'EXERCISED',
];

@Component({
  selector: 'app-positions',
  templateUrl: './positions.component.html',
  styleUrl: './positions.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [StatusBadgeComponent, PositionDrawerComponent],
})
export class PositionsComponent implements OnInit {
  private readonly positionService = inject(PositionService);

  readonly statusOptions = POSITION_STATUSES;

  readonly loading = signal<boolean>(false);
  readonly error = signal<string | null>(null);
  readonly positions = signal<OptionsPosition[]>([]);
  readonly total = signal<number>(0);
  readonly offset = signal<number>(0);
  readonly limit = signal<number>(100);
  readonly underlying = signal<string>('');
  readonly selectedStatus = signal<OptionsPositionStatus | ''>('');
  readonly expandedIds = signal<ReadonlySet<string>>(new Set<string>());

  readonly totalPages = computed(() => Math.ceil(this.total() / this.limit()));
  readonly currentPage = computed(() => Math.floor(this.offset() / this.limit()) + 1);
  readonly hasPrev = computed(() => this.offset() > 0);
  readonly hasNext = computed(() => this.offset() + this.limit() < this.total());

  ngOnInit(): void {
    this.loadPositions();
  }

  loadPositions(): void {
    this.loading.set(true);
    this.error.set(null);

    const params: PositionQueryParams = {
      offset: this.offset(),
      limit: this.limit(),
    };
    if (this.underlying()) params.underlying = this.underlying();
    if (this.selectedStatus()) params.status = this.selectedStatus() as OptionsPositionStatus;

    this.positionService.getPositions(params).subscribe({
      next: (response) => {
        this.positions.set(response.options_items);
        this.total.set(response.total);
        this.loading.set(false);
      },
      error: (err: { message?: string }) => {
        this.error.set(err?.message ?? 'Failed to load positions.');
        this.loading.set(false);
      },
    });
  }

  toggleDrawer(id: string): void {
    const current = this.expandedIds();
    if (current.has(id)) {
      this.expandedIds.set(new Set([...current].filter((i) => i !== id)));
    } else {
      this.expandedIds.set(new Set([...current, id]));
    }
  }

  isExpanded(id: string): boolean {
    return this.expandedIds().has(id);
  }

  pnlClass(pnl: string | null): string {
    if (!pnl) return '';
    return parseFloat(pnl) >= 0 ? 'positive' : 'negative';
  }

  onUnderlyingChange(event: Event): void {
    this.underlying.set((event.target as HTMLInputElement).value);
    this.offset.set(0);
    this.loadPositions();
  }

  onStatusChange(event: Event): void {
    this.selectedStatus.set(
      (event.target as HTMLSelectElement).value as OptionsPositionStatus | '',
    );
    this.offset.set(0);
    this.loadPositions();
  }

  resetFilters(): void {
    this.underlying.set('');
    this.selectedStatus.set('');
    this.offset.set(0);
    this.loadPositions();
  }

  prevPage(): void {
    this.offset.set(Math.max(0, this.offset() - this.limit()));
    this.loadPositions();
  }

  nextPage(): void {
    this.offset.set(this.offset() + this.limit());
    this.loadPositions();
  }

  onLimitChange(event: Event): void {
    this.limit.set(Number((event.target as HTMLSelectElement).value));
    this.offset.set(0);
    this.loadPositions();
  }
}
