import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'dashboard',
    pathMatch: 'full',
  },
  {
    path: 'dashboard',
    loadComponent: () =>
      import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
  },
  {
    path: 'upload',
    loadComponent: () =>
      import('./features/upload/upload.component').then((m) => m.UploadComponent),
  },
  {
    path: 'transactions',
    loadComponent: () =>
      import('./features/transactions/transactions.component').then((m) => m.TransactionsComponent),
  },
  {
    path: 'positions',
    loadComponent: () =>
      import('./features/positions/positions.component').then((m) => m.PositionsComponent),
  },
  {
    path: 'upload-history',
    loadComponent: () =>
      import('./features/upload-history/upload-history.component').then(
        (m) => m.UploadHistoryComponent,
      ),
  },
  {
    path: 'pnl-summary',
    loadComponent: () =>
      import('./features/pnl-summary/pnl-summary.component').then((m) => m.PnlSummaryComponent),
  },
  {
    path: '**',
    redirectTo: 'dashboard',
  },
];
