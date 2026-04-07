import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { OptionsPositionDetail } from '@core/models/position.model';
import { PositionService } from '@core/services/position.service';

@Component({
  selector: 'app-position-drawer',
  templateUrl: './position-drawer.component.html',
  styleUrl: './position-drawer.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe],
})
export class PositionDrawerComponent implements OnInit {
  readonly positionId = input.required<string>();
  private readonly positionService = inject(PositionService);

  readonly loading = signal<boolean>(false);
  readonly error = signal<string | null>(null);
  readonly detail = signal<OptionsPositionDetail | null>(null);

  ngOnInit(): void {
    this.loadDetail();
  }

  loadDetail(): void {
    this.loading.set(true);
    this.error.set(null);
    this.positionService.getPosition(this.positionId()).subscribe({
      next: (d) => {
        this.detail.set(d);
        this.loading.set(false);
      },
      error: (err: { message?: string }) => {
        this.error.set(err?.message ?? 'Failed to load position details.');
        this.loading.set(false);
      },
    });
  }

  pnlClass(amount: string): string {
    return parseFloat(amount) >= 0 ? 'positive' : 'negative';
  }
}
