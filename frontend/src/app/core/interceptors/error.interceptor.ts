import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { ApiError } from '../models/api-error.model';

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      const apiError: ApiError = {
        status: error.status,
        message: error.error?.detail !== undefined ? String(error.error.detail) : error.message,
        ...(error.error?.detail !== undefined && { detail: error.error.detail }),
      };
      console.error('[HTTP Error]', apiError.status, apiError.message, apiError);
      return throwError(() => apiError);
    }),
  );
};
