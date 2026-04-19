"""
The PRD Generation Prompt — core secret sauce of PRDGenius.
"""

PRD_SYSTEM_PROMPT = """You are a world-class Senior Product Manager who has worked at Google, Meta, and Amazon.
You write PRDs that are clear, structured, data-driven, and immediately actionable by engineering and design teams.
Your PRDs are known for being specific (never vague), honest about trade-offs, and aligned with business goals.
You write in a confident, direct tone — no filler words, no corporate fluff.
Always output valid Markdown."""

def build_prd_prompt(feature_name, user_problem, target_users, context, company_stage, author_name, format_style="google"):
    import datetime
    today = datetime.date.today().strftime("%B %d, %Y")

    base_context = f"""
Feature / Initiative: {feature_name}
User Problem: {user_problem}
Target Users: {target_users}
Additional Context: {context}
Company Stage: {company_stage}
Author: {author_name}
Today's Date: {today}
"""

    if format_style == "amazon":
        return f"""
{base_context}

Generate a complete Amazon-style PRD using the Working Backwards methodology.
Start with a Press Release, followed by a Customer FAQ, then the full product spec.
Use proper Markdown headers, tables, and formatting throughout.
Be specific — use real numbers and targets, never placeholders like [X]%.

---

# {feature_name} — Product Requirements Document

**Author:** {author_name} | **Date:** {today} | **Version:** 1.0 | **Status:** Draft

---

## Press Release (Working Backwards)

Write a 4-paragraph press release announcing this feature as if it has just launched:
- Paragraph 1: Headline and what it is
- Paragraph 2: The customer problem it solves and a customer quote
- Paragraph 3: A company spokesperson quote on why this matters
- Paragraph 4: How to get started / call to action

---

## Customer FAQ

List 8-10 questions a customer would ask, with clear answers. Mix happy-path and edge-case questions.

---

## Executive Summary

2-3 sentence TL;DR: What are we building, for whom, and what is the expected impact?

---

## Problem Statement

### The Problem
[Specific, evidence-based description]

### Why Now?
[Market timing, competitive pressure, user research signals]

### Evidence
[Data points, user research, support tickets that validate this problem]

---

## Goals and Non-Goals

### Goals
| Goal | Success Metric | Target | Timeline |
|------|---------------|--------|----------|
| [Primary goal] | [Metric] | [Number] | [Date] |

### Non-Goals
- [What this feature will NOT do]
- [Scope boundaries]
- [Future phase items]

---

## Users and Use Cases

### Primary User Persona
**[Persona Name]** — [1-sentence description]
- Pain: [Their specific pain]
- Goal: [What they are trying to accomplish]

### Key Use Cases
1. **[Use Case 1]:** As a [user], I want [X] so that [Y]
2. **[Use Case 2]:** As a [user], I want [X] so that [Y]
3. **[Use Case 3]:** As a [user], I want [X] so that [Y]

---

## Product Requirements

### P0 — Must Have
| # | Requirement | Rationale |
|---|-------------|-----------|
| P0-1 | [Requirement] | [Why launch blocker] |
| P0-2 | [Requirement] | [Why launch blocker] |

### P1 — Should Have
| # | Requirement | Rationale |
|---|-------------|-----------|
| P1-1 | [Requirement] | [Business rationale] |

### P2 — Nice to Have
| # | Requirement | Rationale |
|---|-------------|-----------|
| P2-1 | [Requirement] | [Why deprioritized] |

---

## Technical Considerations

### Architecture Notes
[High-level approach]

### Performance Requirements
- Load time: < 500ms (p95)
- Uptime SLA: 99.9%

### Dependencies
| Dependency | Team | Risk | Notes |
|------------|------|------|-------|
| [Dep 1] | [Owner] | Medium | [Note] |

---

## Success Metrics

### North Star Metric
**[One metric that best captures user value]** — Target: specific number in specific timeframe

### Supporting Metrics
| Metric | Baseline | Target | Method |
|--------|----------|--------|--------|
| [Metric 1] | [Now] | [Goal] | [How] |

### Events to Track
- feature_viewed: user lands on the feature
- feature_completed: user succeeds
- feature_abandoned: user exits without completing

---

## Launch Plan

| Phase | Audience | Duration | Exit Criteria |
|-------|----------|----------|---------------|
| Alpha | Internal team | 1 week | No P0 bugs |
| Beta | 10% of users | 2 weeks | Metrics met |
| GA | All users | ongoing | Stable 48h |

### Rollback Plan
If error rate exceeds threshold, disable feature flag within 30 minutes.

---

## Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [Risk 1] | Medium | High | [Mitigation] |

---

## Open Questions

| # | Question | Owner | Due | Status |
|---|----------|-------|-----|--------|
| 1 | [Question] | [Role] | [Date] | Open |
"""

    elif format_style == "linear":
        return f"""
{base_context}

Generate a Linear/modern startup-style PRD. Concise, fast-moving, opinionated.
Be specific — use real numbers, never placeholders like [X]%.

---

# {feature_name}

**Author:** {author_name} | **Date:** {today} | **Status:** Draft

---

## Summary
[2 sentences max. What we are building and why it matters right now.]

---

## Problem
[Specific and brutal. What breaks today? Who feels the pain and how often?]

---

## Insight
[The non-obvious observation that makes our solution work.]

---

## Solution
[What we are building, described as the user would experience it.]

---

## Scope

**In scope:**
- [Item 1]
- [Item 2]

**Out of scope:**
- [Item 1]
- [Item 2]

---

## User Stories
- As a [user], I want to [action] so that [outcome]
- As a [user], I want to [action] so that [outcome]
- As a [user], I want to [action] so that [outcome]

---

## Requirements

**Must ship:**
- [ ] [Requirement]
- [ ] [Requirement]

**Should ship:**
- [ ] [Requirement]

**Will not ship this cycle:**
- [ ] [Requirement]

---

## Success Metrics
| Metric | Now | Goal | Timeline |
|--------|-----|------|----------|
| [Primary metric] | [Specific number] | [Specific target] | [Date] |

---

## Risks
- **[Risk]:** [Mitigation]

---

## Open Questions
- [ ] [Question] — owner: [Name]

---

## Timeline
| Milestone | Date |
|-----------|------|
| Design complete | [Date] |
| Eng kickoff | [Date] |
| Alpha | [Date] |
| Launch | [Date] |
"""

    else:
        return f"""
{base_context}

Generate a complete, FAANG-quality PRD in Google/Meta style.
Detailed enough that an engineering team could start building immediately.
Use proper Markdown: headers, tables, bullet points, checkboxes.
CRITICAL: Use real numbers and specific targets — never write [X]% or [N] days.
Infer reasonable, realistic metrics from the context provided.

---

# {feature_name} — Product Requirements Document

**Author:** {author_name}
**Date:** {today}
**Version:** 1.0
**Status:** Draft
**Reviewers:** Engineering Lead · Design Lead · Data/Analytics Lead

---

## Executive Summary

[3-sentence summary: (1) What we are building, (2) Who it is for and what problem it solves, (3) Expected business impact with a specific metric.]

---

## Problem Statement

### Background
[2-3 sentences of context. What is the current state? What exists today?]

### The Problem
[Specific and brutal. What exactly breaks? Who feels it? How often?]

### Why Now?
[Market timing, competitive pressure, user research, strategic priority.]

### Evidence
- [Data point 1: user research, analytics, support data with real numbers]
- [Data point 2]
- "[Illustrative user quote that captures the pain]"

---

## Goals

### Primary Goal
[One sentence. The single most important outcome.]

### Success Metrics
| Metric | Current Baseline | Target | Timeframe |
|--------|-----------------|--------|-----------|
| [Primary metric] | [Specific number] | [Specific target] | [X weeks post-launch] |
| [Secondary metric] | [Specific number] | [Specific target] | [X weeks] |
| [Retention/engagement metric] | [Specific number] | [Specific target] | [X weeks] |

### Non-Goals
- [Non-goal 1 and why]
- [Non-goal 2 and why]
- [Non-goal 3 and why]

---

## Users and Use Cases

### Primary Persona
**[Persona Name]** — [Role/Description]
> "[One-sentence quote capturing their perspective on this problem]"

- **Frequency of pain:** [Daily / Weekly / Per event]
- **Current workaround:** [What they do today]
- **Cost of problem:** [Time lost, revenue impact, frustration level]

### User Journey: Today vs. After

| Step | Today (Painful) | After Launch (Smooth) |
|------|----------------|----------------------|
| [Step 1] | [Current experience] | [Future experience] |
| [Step 2] | [Current experience] | [Future experience] |
| [Step 3] | [Current experience] | [Future experience] |

### Key Use Cases
1. **Happy Path:** [Description]
2. **Power User:** [Description]
3. **Edge Case:** [Description]
4. **Error Recovery:** [Description]

---

## Product Requirements

### P0 — Must Have (Ship Blockers)

| ID | Requirement | User Story | Acceptance Criteria |
|----|-------------|------------|---------------------|
| P0-1 | [Requirement] | As a [user], I want [X] so that [Y] | [Specific, testable criteria] |
| P0-2 | [Requirement] | As a [user], I want [X] so that [Y] | [Specific, testable criteria] |
| P0-3 | [Requirement] | As a [user], I want [X] so that [Y] | [Specific, testable criteria] |

### P1 — Should Have

| ID | Requirement | Rationale | Fallback if Cut |
|----|-------------|-----------|-----------------|
| P1-1 | [Requirement] | [Why important] | [Fallback plan] |
| P1-2 | [Requirement] | [Why important] | [Fallback plan] |

### P2 — Nice to Have

| ID | Requirement | Why Deprioritized |
|----|-------------|-------------------|
| P2-1 | [Requirement] | [Reason] |

---

## Design and UX

### Design Principles
1. **[Principle]:** [How it applies to this feature]
2. **[Principle]:** [How it applies to this feature]
3. **[Principle]:** [How it applies to this feature]

### Key Flows

**Happy Path:**
[Entry point] -> [Step 1] -> [Step 2] -> [Step 3] -> [Success state]

**Error Flow:**
[Entry point] -> [Step 1] -> [Error trigger] -> [Error message] -> [Recovery]

### Accessibility
- WCAG 2.1 AA compliance required
- [Specific accessibility considerations for this feature]

---

## Technical Considerations

### Architecture
[High-level approach. What systems are involved? New vs. reused?]

### Performance Requirements
- Page load: < 500ms (p95)
- API response: < 2s (p99)
- Uptime SLA: 99.9%

### Data and Privacy
- Data classification: [Public / Internal / Confidential]
- PII involved: [Yes/No]
- Retention: [X days/years]
- Compliance: [GDPR, CCPA, etc. as applicable]

### Dependencies
| Dependency | Team | Status | Risk |
|------------|------|--------|------|
| [Dep 1] | [Owner] | Ready / In Progress | Low/Med/High |
| [Dep 2] | [Owner] | Ready / In Progress | Low/Med/High |

---

## Analytics and Instrumentation

### Events to Track
| Event | Trigger | Key Properties |
|-------|---------|----------------|
| feature_viewed | User lands on feature | user_id, source, timestamp |
| feature_started | User begins core action | user_id, entry_point |
| feature_completed | User succeeds | user_id, time_to_complete_ms |
| feature_abandoned | User exits without finishing | user_id, last_step, reason |
| error_shown | Any error displayed | user_id, error_type, step |

### Dashboards to Build
- [ ] Funnel: Entry -> Core action -> Completion with drop-off rates
- [ ] Daily/Weekly active usage trend
- [ ] Error rate by type
- [ ] [Feature-specific metric dashboard]

---

## Launch Plan

| Phase | Audience | Duration | Exit Criteria |
|-------|----------|----------|---------------|
| Alpha | Internal team only | 1 week | Zero P0 bugs, team satisfied |
| Beta | 10% of target segment | 2 weeks | Primary metric at target |
| GA | All users | ongoing | Stable for 48h post full rollout |

### Rollout
- Feature flag: [flag_name]
- Ramp: 1% -> 10% -> 50% -> 100% with 24h between steps

### Rollback Plan
**Trigger:** Error rate exceeds 2% or primary metric drops 15% below baseline
**Action:** Disable feature flag within 30 minutes
**Owner:** Engineering on-call

---

## Risks

| Risk | Probability | Impact | Mitigation | Owner |
|------|-------------|--------|------------|-------|
| [Risk 1] | Medium | High | [Specific mitigation strategy] | [Role] |
| [Risk 2] | Low | High | [Specific mitigation strategy] | [Role] |
| [Risk 3] | High | Low | [Specific mitigation strategy] | [Role] |

---

## Open Questions

| # | Question | Why It Matters | Owner | Due | Status |
|---|----------|---------------|-------|-----|--------|
| 1 | [Question] | [Impact if unresolved] | [Role] | [Date] | Open |
| 2 | [Question] | [Impact if unresolved] | [Role] | [Date] | Open |

---

## Appendix

### Revision History
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | {today} | {author_name} | Initial draft |
"""
