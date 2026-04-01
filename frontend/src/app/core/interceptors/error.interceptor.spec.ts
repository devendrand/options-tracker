import { TestBed } from '@angular/core/testing';
import {
  HttpClient,
  HttpStatusCode,
  provideHttpClient,
  withInterceptors,
} from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { errorInterceptor } from './error.interceptor';
import { ApiError } from '../models/api-error.model';

describe('errorInterceptor', () => {
  let http: HttpClient;
  let controller: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    controller.verify();
  });

  it('should pass through successful responses unchanged', (done) => {
    http.get<{ ok: boolean }>('/test').subscribe({
      next: (res) => {
        expect(res).toEqual({ ok: true });
        done();
      },
      error: () => done.fail('should not error'),
    });

    controller.expectOne('/test').flush({ ok: true });
  });

  it('should re-throw a 400 error as ApiError with detail', (done) => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    http.get('/test').subscribe({
      next: () => done.fail('should not succeed'),
      error: (err: ApiError) => {
        expect(err.status).toBe(HttpStatusCode.BadRequest);
        expect(err.message).toBe('Bad request');
        expect(err.detail).toBe('Bad request');
        expect(consoleSpy).toHaveBeenCalled();
        consoleSpy.mockRestore();
        done();
      },
    });

    controller
      .expectOne('/test')
      .flush(
        { detail: 'Bad request' },
        { status: HttpStatusCode.BadRequest, statusText: 'Bad Request' },
      );
  });

  it('should re-throw a 404 error as ApiError with detail', (done) => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    http.get('/test').subscribe({
      next: () => done.fail('should not succeed'),
      error: (err: ApiError) => {
        expect(err.status).toBe(HttpStatusCode.NotFound);
        expect(err.message).toBe('Not found');
        expect(err.detail).toBe('Not found');
        expect(consoleSpy).toHaveBeenCalled();
        consoleSpy.mockRestore();
        done();
      },
    });

    controller
      .expectOne('/test')
      .flush({ detail: 'Not found' }, { status: HttpStatusCode.NotFound, statusText: 'Not Found' });
  });

  it('should re-throw a 422 validation error with FastAPI detail array accessible', (done) => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const validationDetail = [
      { loc: ['body', 'file'], msg: 'field required', type: 'value_error.missing' },
    ];

    http.get('/test').subscribe({
      next: () => done.fail('should not succeed'),
      error: (err: ApiError) => {
        expect(err.status).toBe(HttpStatusCode.UnprocessableEntity);
        expect(err.detail).toEqual(validationDetail);
        expect(Array.isArray(err.detail)).toBe(true);
        expect(consoleSpy).toHaveBeenCalled();
        consoleSpy.mockRestore();
        done();
      },
    });

    controller
      .expectOne('/test')
      .flush(
        { detail: validationDetail },
        { status: HttpStatusCode.UnprocessableEntity, statusText: 'Unprocessable Entity' },
      );
  });

  it('should re-throw a 500 error as ApiError with detail', (done) => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    http.get('/test').subscribe({
      next: () => done.fail('should not succeed'),
      error: (err: ApiError) => {
        expect(err.status).toBe(HttpStatusCode.InternalServerError);
        expect(err.detail).toBe('Internal Server Error');
        expect(consoleSpy).toHaveBeenCalled();
        consoleSpy.mockRestore();
        done();
      },
    });

    controller
      .expectOne('/test')
      .flush(
        { detail: 'Internal Server Error' },
        { status: HttpStatusCode.InternalServerError, statusText: 'Internal Server Error' },
      );
  });

  it('should re-throw a network error (status=0) as ApiError without detail', (done) => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    http.get('/test').subscribe({
      next: () => done.fail('should not succeed'),
      error: (err: ApiError) => {
        expect(err.status).toBe(0);
        expect(err.detail).toBeUndefined();
        expect(err.message).toBeTruthy();
        expect(consoleSpy).toHaveBeenCalled();
        consoleSpy.mockRestore();
        done();
      },
    });

    controller.expectOne('/test').error(new ProgressEvent('error'));
  });

  it('should use HttpErrorResponse message when no detail field present', (done) => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    http.get('/test').subscribe({
      next: () => done.fail('should not succeed'),
      error: (err: ApiError) => {
        expect(err.status).toBe(HttpStatusCode.BadGateway);
        expect(err.detail).toBeUndefined();
        expect(err.message).toBeTruthy();
        expect(consoleSpy).toHaveBeenCalled();
        consoleSpy.mockRestore();
        done();
      },
    });

    controller
      .expectOne('/test')
      .flush(
        { error: 'no detail field here' },
        { status: HttpStatusCode.BadGateway, statusText: 'Bad Gateway' },
      );
  });
});
