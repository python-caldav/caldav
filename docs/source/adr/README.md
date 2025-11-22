# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the caldav library.

ADRs are documents that capture important architectural decisions made during the project's development, along with their context and consequences.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](./0001-httpx-async-first-architecture.md) | HTTPX Async-First Architecture with Thin Sync Wrappers | Proposed |

## ADR Status Definitions

- **Proposed**: Under discussion, not yet accepted
- **Accepted**: Approved and ready for implementation
- **Deprecated**: No longer relevant or superseded
- **Superseded**: Replaced by another ADR

## Template

When creating a new ADR, use this structure:

```markdown
# ADR NNNN: Title

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXXX]

## Context
What is the issue that we're seeing that is motivating this decision?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult to do because of this change?
```
