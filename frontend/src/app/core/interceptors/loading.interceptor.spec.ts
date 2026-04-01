import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { loadingInterceptor } from './loading.interceptor';
import { LoadingService } from '../services/loading.service';

describe('loadingInterceptor', () => {
  let http: HttpClient;
  let controller: HttpTestingController;
  let loadingService: LoadingService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([loadingInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    controller = TestBed.inject(HttpTestingController);
    loadingService = TestBed.inject(LoadingService);
  });

  afterEach(() => {
    controller.verify();
  });

  it('should increment loading on request start', () => {
    http.get('/test').subscribe();
    expect(loadingService.isLoading).toBe(true);
    controller.expectOne('/test').flush({ ok: true });
  });

  it('should decrement loading on successful response', () => {
    http.get('/test').subscribe();
    expect(loadingService.isLoading).toBe(true);
    controller.expectOne('/test').flush({ ok: true });
    expect(loadingService.isLoading).toBe(false);
  });

  it('should decrement loading on error response', () => {
    http.get('/test').subscribe({ error: () => {} });
    expect(loadingService.isLoading).toBe(true);
    controller.expectOne('/test').flush('fail', { status: 500, statusText: 'Error' });
    expect(loadingService.isLoading).toBe(false);
  });

  it('should track multiple concurrent requests', () => {
    http.get('/test1').subscribe();
    http.get('/test2').subscribe();
    expect(loadingService.isLoading).toBe(true);

    controller.expectOne('/test1').flush({ ok: true });
    expect(loadingService.isLoading).toBe(true);

    controller.expectOne('/test2').flush({ ok: true });
    expect(loadingService.isLoading).toBe(false);
  });

  it('should decrement on network error', () => {
    http.get('/test').subscribe({ error: () => {} });
    expect(loadingService.isLoading).toBe(true);
    controller.expectOne('/test').error(new ProgressEvent('error'));
    expect(loadingService.isLoading).toBe(false);
  });
});
