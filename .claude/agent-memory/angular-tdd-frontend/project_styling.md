---
name: Styling Architecture
description: CSS approach for options-tracker — component SCSS files, no global frameworks, design tokens
type: project
---

Component-level SCSS is used for all feature styling. No global CSS frameworks (no Tailwind, no Bootstrap).

**Why:** Keeps styles encapsulated per Angular's recommendation. Easy to audit.

**Design tokens used:**
- Primary: #1a73e8
- Positive/Success: #0d9488 (teal-green)
- Negative/Danger: #dc2626 (red)
- Warning: #f59e0b (amber)
- Background: #f8fafc
- Card bg: #ffffff
- Border: #e2e8f0
- Text: #1e293b / Muted: #64748b

**Status badge colors** are defined as inline `styles` array in `status-badge.component.ts` using `.status-badge--{status_lowercase}` classes.

**How to apply:** When adding new components, add a `.scss` file and reference it with `styleUrl` in the decorator. Use the design tokens above for consistency. Match the existing table/filter-bar/pagination patterns from transactions or positions components.
