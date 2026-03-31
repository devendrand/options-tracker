import { TestBed } from '@angular/core/testing';
import { UploadHistoryComponent } from './upload-history.component';

describe('UploadHistoryComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UploadHistoryComponent],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(UploadHistoryComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });
});
