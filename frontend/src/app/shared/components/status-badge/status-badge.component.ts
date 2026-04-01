import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-status-badge',
  template: `<span
    data-testid="status-badge"
    [class]="'status-badge status-badge--' + status().toLowerCase()"
    >{{ status() }}</span
  >`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatusBadgeComponent {
  readonly status = input.required<string>();
}
