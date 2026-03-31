import { DatePipe } from '@angular/common';
import { inject, Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'relativeDate',
  pure: true,
})
export class RelativeDatePipe implements PipeTransform {
  private readonly datePipe = inject(DatePipe);

  transform(value: string | null | undefined): string | null {
    if (!value) {
      return null;
    }
    return this.datePipe.transform(value, 'MMM d, yyyy', 'UTC');
  }
}
