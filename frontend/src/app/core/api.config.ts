import { InjectionToken } from '@angular/core';
import { EnvironmentProviders, makeEnvironmentProviders } from '@angular/core';

export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  factory: () => '/api/v1',
});

export function provideApiConfig(baseUrl?: string): EnvironmentProviders {
  return makeEnvironmentProviders([
    {
      provide: API_BASE_URL,
      useValue: baseUrl ?? '/api/v1',
    },
  ]);
}
