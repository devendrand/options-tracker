import { TestBed } from '@angular/core/testing';
import { UploadComponent } from './upload.component';

describe('UploadComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UploadComponent],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(UploadComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });
});
