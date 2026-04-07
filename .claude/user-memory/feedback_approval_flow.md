---
name: Reduce approval friction
description: User finds too many tech-lead approval prompts disruptive — batch reviews, auto-approve mechanical fixes
type: feedback
---

User finds the tech-lead review/approval flow too heavy — "too much to approve as lead."

**Why:** Each feature generates a plan review + implementation review + fix re-review cycle. With 19 features this creates excessive back-and-forth that slows progress.

**How to apply:** On resume, restructure the workflow:
- Tech lead should batch-review completed features rather than reviewing each plan before implementation starts
- Mechanical fixes (formatting, mypy plugin) should be applied directly without round-tripping through tech lead
- Only escalate to tech lead for architectural decisions, design disagreements, or quality gate failures that indicate real problems
- Let implementing agents write plans AND implement in one pass, then tech lead reviews the finished work
