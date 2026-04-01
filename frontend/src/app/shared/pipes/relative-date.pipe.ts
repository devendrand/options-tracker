import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'relativeDate',
  pure: true,
})
export class RelativeDatePipe implements PipeTransform {
  transform(value: string | null | undefined): string | null {
    if (!value) {
      return null;
    }
    // If value is already an ISO string with time, use as-is; otherwise append UTC midnight
    const date = new Date(value.includes('T') ? value : value + 'T00:00:00Z');
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      timeZone: 'UTC',
    });
  }
}
