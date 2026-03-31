import { DatePipe } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { RelativeDatePipe } from './relative-date.pipe';

describe('RelativeDatePipe', () => {
  let pipe: RelativeDatePipe;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [RelativeDatePipe, DatePipe],
    });
    pipe = TestBed.inject(RelativeDatePipe);
  });

  it('should transform a YYYY-MM-DD date string to "MMM d, yyyy" format', () => {
    expect(pipe.transform('2026-03-15')).toBe('Mar 15, 2026');
  });

  it('should handle UTC midnight ISO string without timezone shift (2026-03-15T00:00:00Z → Mar 15, 2026)', () => {
    // Without UTC param, new Date('2026-03-15T00:00:00Z') renders as Mar 14 in UTC-N timezones.
    // Angular DatePipe with 'UTC' ensures we always display the calendar date as-is.
    expect(pipe.transform('2026-03-15T00:00:00Z')).toBe('Mar 15, 2026');
  });

  it('should return null when value is null', () => {
    expect(pipe.transform(null)).toBeNull();
  });

  it('should return null when value is undefined', () => {
    expect(pipe.transform(undefined)).toBeNull();
  });

  it('should return null when value is an empty string', () => {
    expect(pipe.transform('')).toBeNull();
  });
});
