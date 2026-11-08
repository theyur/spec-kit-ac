# Feature Specification: Order discount

**Feature Branch**: `001-order-discount`

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "Orders of 100.00 or more get 10 % off."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discount for larger orders (Priority: P1)

A customer whose order subtotal reaches 100.00 pays 10 % less. Smaller orders pay the subtotal.

**Why this priority**: It is the whole feature.

**Independent Test**: Compute the total for subtotals below, at and above 100.00 and compare it with the
expected amount.

**Acceptance Scenarios**:

1. **Given** an order with a subtotal of at least 100.00, **When** the total is calculated, **Then** the
   total is the subtotal minus 10 %.
2. **Given** an order with a subtotal below 100.00, **When** the total is calculated, **Then** the total is
   the subtotal, unchanged.
3. **Given** an order whose discounted total has more than 2 decimals, **When** the total is calculated,
   **Then** the total is rounded to 2 decimals, midpoint away from zero.

---

### User Story 2 - Invalid subtotal (Priority: P2)

A subtotal cannot be negative. The calculator rejects it instead of returning a total.

**Why this priority**: It protects callers from silently wrong totals.

**Independent Test**: Compute the total for a negative subtotal and observe the rejection.

**Acceptance Scenarios**:

1. **Given** an order with a negative subtotal, **When** the total is calculated, **Then** the calculation
   is rejected with an `ArgumentOutOfRangeException`.

---

### Edge Cases

- A subtotal of exactly 100.00 gets the discount.
- A subtotal of 0.00 is valid and gives a total of 0.00.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `DiscountCalculator.Total` MUST return the subtotal minus 10 % when the subtotal is 100.00 or
  more.
- **FR-002**: `DiscountCalculator.Total` MUST return the subtotal unchanged when the subtotal is below
  100.00.
- **FR-003**: `DiscountCalculator.Total` MUST throw an `ArgumentOutOfRangeException` when the subtotal is
  negative.
- **FR-004**: The total MUST be rounded to 2 decimals, with midpoints rounded away from zero
  (`MidpointRounding.AwayFromZero`).

### Key Entities

- **Order subtotal**: a `decimal` amount, the sum of the order lines before any discount.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every order of 100.00 or more is charged exactly 90 % of its subtotal, rounded as in FR-004.

## Assumptions

- Amounts have no currency; all orders use the same one.
