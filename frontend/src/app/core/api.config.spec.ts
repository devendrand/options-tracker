import { TestBed } from '@angular/core/testing';
import { API_BASE_URL, provideApiConfig } from './api.config';

describe('API_BASE_URL token', () => {
  it('should provide the default value "/api/v1" via the token factory', () => {
    TestBed.configureTestingModule({});
    const baseUrl = TestBed.inject(API_BASE_URL);
    expect(baseUrl).toBe('/api/v1');
  });
});

describe('provideApiConfig()', () => {
  it('should provide a custom base URL when specified', () => {
    TestBed.configureTestingModule({
      providers: [provideApiConfig('http://localhost:8000/api/v1')],
    });
    const baseUrl = TestBed.inject(API_BASE_URL);
    expect(baseUrl).toBe('http://localhost:8000/api/v1');
  });

  it('should fall back to "/api/v1" when no URL is specified', () => {
    TestBed.configureTestingModule({
      providers: [provideApiConfig()],
    });
    const baseUrl = TestBed.inject(API_BASE_URL);
    expect(baseUrl).toBe('/api/v1');
  });
});
