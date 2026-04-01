import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-status-badge',
  template: `<span
    data-testid="status-badge"
    [class]="'status-badge status-badge--' + status().toLowerCase()"
    >{{ status() }}</span
  >`,
  styles: [`
    .status-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      background: #e2e8f0;
      color: #475569;
    }

    .status-badge--active,
    .status-badge--open,
    .status-badge--completed {
      background: #d1fae5;
      color: #065f46;
    }

    .status-badge--closed,
    .status-badge--expired {
      background: #e2e8f0;
      color: #475569;
    }

    .status-badge--duplicate {
      background: #fef9c3;
      color: #854d0e;
    }

    .status-badge--possible_duplicate,
    .status-badge--partially_closed {
      background: #ffedd5;
      color: #c2410c;
    }

    .status-badge--parse_error,
    .status-badge--failed {
      background: #fee2e2;
      color: #991b1b;
    }

    .status-badge--assigned,
    .status-badge--exercised {
      background: #ede9fe;
      color: #5b21b6;
    }

    .status-badge--processing {
      background: #dbeafe;
      color: #1e40af;
    }
  `],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatusBadgeComponent {
  readonly status = input.required<string>();
}
