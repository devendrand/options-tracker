---
name: Angular Stack Details
description: Angular 21 + Jest + ESLint setup specifics for options-tracker frontend
type: project
---

Angular 21.2.5 (latest at 2026-03-30) with zoneless change detection by default (no zone.js).

**Why:** Angular CLI latest installs 21.x; zoneless is the new default since Angular 19.

**Key setup choices:**
- `jest-preset-angular` v16 — uses `setup-env/zoneless` (not zone) for `setupFilesAfterEnv`
- ESLint 9.x — ESLint 10 broke `@angular-eslint/builder` v21 (removed legacy API options); must stay at ^9
- `jest-environment-jsdom` must be installed separately (not bundled since Jest 28)
- `app.config.ts` excluded from coverage (pure config, no logic)
- `app.routes.ts` excluded from coverage (pure route definitions)
- `tsconfig.spec.json` uses `"module": "CommonJS"` and `"esModuleInterop": true` for Jest compatibility
- `@angular/cdk` installed from day 1 (required for drawer in F-17)
- `@angular-eslint/prefer-inject` rule is active — must use `inject()` not constructor DI
- Pipe specs use `TestBed.inject()` not `new Pipe()` because `inject()` requires Angular context

**How to apply:** When adding new services/pipes, use `inject()` fn. When writing pipe specs, provide the pipe and its deps via `TestBed.configureTestingModule({ providers: [...] })` and get instance with `TestBed.inject()`.
