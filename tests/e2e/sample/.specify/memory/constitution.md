# Shop Constitution

## Core Principles

### I. Library first

`Shop.Pricing` is a class library with a small public API. Every public type and member has an XML
documentation comment.

### II. Money is exact

Amounts are `decimal`. A requirement that rounds says how (number of decimals and the midpoint rule).

### III. Tests with every change

Every behaviour change comes with unit tests in `tests/Shop.Pricing.Tests`.

### IV. Testability

- Time comes from an injected `TimeProvider`, never from `DateTime.Now` / `DateTimeOffset.UtcNow`.
- External effects (files, network, databases) sit behind public interfaces with test doubles.
- Errors are observable through the public API: an exception type or a result value, never only a log
  line.
- The system can be built with test doubles through public constructors or factories.
- No `InternalsVisibleTo` in the projects whose public API the acceptance tests use.

## Governance

This constitution overrides other practices. Amendments are made with `/speckit-constitution`.

**Version**: 1.0.0 | **Ratified**: 2026-11-08 | **Last Amended**: 2026-11-08
