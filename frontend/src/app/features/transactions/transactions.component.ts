import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { DatePipe, SlicePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import {
  Transaction,
  TransactionCategory,
  TransactionQueryParams,
} from '@core/models/transaction.model';
import { TransactionService } from '@core/services/transaction.service';
import { CategoryLabelPipe } from '@shared/pipes/category-label.pipe';
import { RelativeDatePipe } from '@shared/pipes/relative-date.pipe';
import { StatusBadgeComponent } from '@shared/components/status-badge/status-badge.component';

export const TRANSACTION_CATEGORIES: TransactionCategory[] = [
  'OPTIONS_SELL_TO_OPEN',
  'OPTIONS_BUY_TO_OPEN',
  'OPTIONS_BUY_TO_CLOSE',
  'OPTIONS_SELL_TO_CLOSE',
  'OPTIONS_EXPIRED',
  'OPTIONS_ASSIGNED',
  'OPTIONS_EXERCISED',
  'EQUITY_BUY',
  'EQUITY_SELL',
  'DIVIDEND',
  'TRANSFER',
  'INTEREST',
  'FEE',
  'JOURNAL',
  'OTHER',
];

export const DEDUP_STATUSES = ['UNIQUE', 'DUPLICATE', 'POSSIBLE_DUPLICATE', 'PARSE_ERROR'];

@Component({
  selector: 'app-transactions',
  templateUrl: './transactions.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    DatePipe,
    SlicePipe,
    RouterLink,
    CategoryLabelPipe,
    RelativeDatePipe,
    StatusBadgeComponent,
  ],
})
export class TransactionsComponent implements OnInit {
  private readonly transactionService = inject(TransactionService);

  readonly categories = TRANSACTION_CATEGORIES;
  readonly dedupStatuses = DEDUP_STATUSES;

  readonly loading = signal<boolean>(false);
  readonly error = signal<string | null>(null);
  readonly transactions = signal<Transaction[]>([]);
  readonly total = signal<number>(0);
  readonly offset = signal<number>(0);
  readonly limit = signal<number>(100);
  readonly symbol = signal<string>('');
  readonly selectedCategories = signal<TransactionCategory[]>([]);
  readonly selectedStatuses = signal<string[]>([]);
  readonly startDate = signal<string>('');
  readonly endDate = signal<string>('');

  readonly totalPages = computed(() => Math.ceil(this.total() / this.limit()));
  readonly currentPage = computed(() => Math.floor(this.offset() / this.limit()) + 1);
  readonly hasPrev = computed(() => this.offset() > 0);
  readonly hasNext = computed(() => this.offset() + this.limit() < this.total());

  ngOnInit(): void {
    this.loadTransactions();
  }

  loadTransactions(): void {
    this.loading.set(true);
    this.error.set(null);

    const params: TransactionQueryParams = {
      offset: this.offset(),
      limit: this.limit(),
    };
    if (this.symbol()) params.symbol = this.symbol();
    if (this.selectedCategories().length) params.category = this.selectedCategories();
    if (this.selectedStatuses().length) params.dedup_status = this.selectedStatuses();
    if (this.startDate()) params.start_date = this.startDate();
    if (this.endDate()) params.end_date = this.endDate();

    this.transactionService.getTransactions(params).subscribe({
      next: (response) => {
        this.transactions.set(response.items);
        this.total.set(response.total);
        this.loading.set(false);
      },
      error: (err: { message?: string }) => {
        this.error.set(err?.message ?? 'Failed to load transactions.');
        this.loading.set(false);
      },
    });
  }

  onCategoryMultiChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const values = Array.from(select.selectedOptions).map(
      (opt) => opt.value as TransactionCategory,
    );
    this.selectedCategories.set(values);
    this.offset.set(0);
    this.loadTransactions();
  }

  onStatusMultiChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const values = Array.from(select.selectedOptions).map((opt) => opt.value);
    this.selectedStatuses.set(values);
    this.offset.set(0);
    this.loadTransactions();
  }

  onSymbolChange(event: Event): void {
    this.symbol.set((event.target as HTMLInputElement).value);
    this.offset.set(0);
    this.loadTransactions();
  }

  onStartDateChange(event: Event): void {
    this.startDate.set((event.target as HTMLInputElement).value);
    this.offset.set(0);
    this.loadTransactions();
  }

  onEndDateChange(event: Event): void {
    this.endDate.set((event.target as HTMLInputElement).value);
    this.offset.set(0);
    this.loadTransactions();
  }

  resetFilters(): void {
    this.selectedCategories.set([]);
    this.selectedStatuses.set([]);
    this.symbol.set('');
    this.startDate.set('');
    this.endDate.set('');
    this.offset.set(0);
    this.loadTransactions();
  }

  prevPage(): void {
    this.offset.set(Math.max(0, this.offset() - this.limit()));
    this.loadTransactions();
  }

  nextPage(): void {
    this.offset.set(this.offset() + this.limit());
    this.loadTransactions();
  }

  onLimitChange(event: Event): void {
    this.limit.set(Number((event.target as HTMLSelectElement).value));
    this.offset.set(0);
    this.loadTransactions();
  }

  rowClass(status: string): string {
    if (status === 'DUPLICATE') return 'row-duplicate';
    if (status === 'POSSIBLE_DUPLICATE') return 'row-possible-duplicate';
    if (status === 'PARSE_ERROR') return 'row-parse-error';
    return '';
  }
}
