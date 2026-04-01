import { TestBed } from '@angular/core/testing';
import { LoadingService } from './loading.service';
import { firstValueFrom } from 'rxjs';

describe('LoadingService', () => {
  let service: LoadingService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(LoadingService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should start with loading$ as false', async () => {
    const loading = await firstValueFrom(service.loading$);
    expect(loading).toBe(false);
  });

  it('should start with isLoading as false', () => {
    expect(service.isLoading).toBe(false);
  });

  it('should emit true on loading$ after increment', async () => {
    service.increment();
    const loading = await firstValueFrom(service.loading$);
    expect(loading).toBe(true);
    expect(service.isLoading).toBe(true);
  });

  it('should emit false on loading$ after increment then decrement', async () => {
    service.increment();
    service.decrement();
    const loading = await firstValueFrom(service.loading$);
    expect(loading).toBe(false);
    expect(service.isLoading).toBe(false);
  });

  it('should stay true when multiple requests are active', async () => {
    service.increment();
    service.increment();
    service.decrement();
    const loading = await firstValueFrom(service.loading$);
    expect(loading).toBe(true);
    expect(service.isLoading).toBe(true);
  });

  it('should not go below zero on extra decrement', async () => {
    service.decrement();
    const loading = await firstValueFrom(service.loading$);
    expect(loading).toBe(false);
    expect(service.isLoading).toBe(false);
  });
});
