import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-positions',
  templateUrl: './positions.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PositionsComponent {}
