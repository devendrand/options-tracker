import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { StatusBadgeComponent } from './status-badge.component';

describe('StatusBadgeComponent', () => {
  function createComponent(status: string) {
    const fixture = TestBed.createComponent(StatusBadgeComponent);
    fixture.componentRef.setInput('status', status);
    fixture.detectChanges();
    return fixture;
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [StatusBadgeComponent],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = createComponent('UNIQUE');
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should display the status text', () => {
    const fixture = createComponent('UNIQUE');
    const badge = fixture.debugElement.query(By.css('[data-testid="status-badge"]'));
    expect(badge.nativeElement.textContent).toBe('UNIQUE');
  });

  it('should apply a lowercase CSS class based on status', () => {
    const fixture = createComponent('DUPLICATE');
    const badge = fixture.debugElement.query(By.css('[data-testid="status-badge"]'));
    expect(badge.nativeElement.classList).toContain('status-badge--duplicate');
  });

  it('should apply status-badge base class', () => {
    const fixture = createComponent('POSSIBLE_DUPLICATE');
    const badge = fixture.debugElement.query(By.css('[data-testid="status-badge"]'));
    expect(badge.nativeElement.classList).toContain('status-badge');
  });

  it('should render POSSIBLE_DUPLICATE status', () => {
    const fixture = createComponent('POSSIBLE_DUPLICATE');
    const badge = fixture.debugElement.query(By.css('[data-testid="status-badge"]'));
    expect(badge.nativeElement.textContent).toBe('POSSIBLE_DUPLICATE');
    expect(badge.nativeElement.classList).toContain('status-badge--possible_duplicate');
  });

  it('should render PARSE_ERROR status', () => {
    const fixture = createComponent('PARSE_ERROR');
    const badge = fixture.debugElement.query(By.css('[data-testid="status-badge"]'));
    expect(badge.nativeElement.textContent).toBe('PARSE_ERROR');
    expect(badge.nativeElement.classList).toContain('status-badge--parse_error');
  });
});
