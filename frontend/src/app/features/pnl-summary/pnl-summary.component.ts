import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-pnl-summary',
  templateUrl: './pnl-summary.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PnlSummaryComponent {}
