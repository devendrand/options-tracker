import { TestBed } from '@angular/core/testing';
import { PositionsComponent } from './positions.component';

describe('PositionsComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PositionsComponent],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(PositionsComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });
});
