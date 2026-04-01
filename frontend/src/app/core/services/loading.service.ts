import { Injectable } from '@angular/core';
import { BehaviorSubject, map } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class LoadingService {
  private readonly activeRequests = new BehaviorSubject<number>(0);
  readonly loading$ = this.activeRequests.pipe(map((count) => count > 0));

  increment(): void {
    this.activeRequests.next(this.activeRequests.value + 1);
  }

  decrement(): void {
    const current = this.activeRequests.value;
    this.activeRequests.next(current > 0 ? current - 1 : 0);
  }

  get isLoading(): boolean {
    return this.activeRequests.value > 0;
  }
}
