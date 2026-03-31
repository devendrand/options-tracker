import { TestBed } from '@angular/core/testing';
import { PnlSummaryComponent } from './pnl-summary.component';

describe('PnlSummaryComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PnlSummaryComponent],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(PnlSummaryComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });
});
