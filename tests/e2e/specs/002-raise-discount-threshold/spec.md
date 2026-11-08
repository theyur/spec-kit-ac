# Feature Specification: Raise the discount threshold

**Feature Branch**: `002-raise-discount-threshold`

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "The 10 % discount now starts at 150.00 instead of 100.00."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discount starts at 150.00 (Priority: P1)

The order discount now starts at a subtotal of 150.00. This **replaces** the threshold of 100.00 from
feature 001 (order discount): orders from 100.00 up to 149.99 no longer get a discount.

**Why this priority**: It is the whole feature.

**Independent Test**: Compute the total for subtotals below, at and above 150.00 and compare it with the
expected amount.

**Acceptance Scenarios**:

1. **Given** an order with a subtotal of at least 150.00, **When** the total is calculated, **Then** the
   total is the subtotal minus 10 %.
2. **Given** an order with a subtotal below 150.00, including subtotals from 100.00 to 149.99, **When** the
   total is calculated, **Then** the total is the subtotal, unchanged.

---

### Edge Cases

- A subtotal of exactly 150.00 gets the discount.
- A subtotal of exactly 100.00 (discounted before this feature) no longer gets it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `DiscountCalculator.Total` MUST return the subtotal minus 10 % when the subtotal is 150.00 or
  more (previously 100.00, feature 001).
- **FR-002**: `DiscountCalculator.Total` MUST return the subtotal unchanged when the subtotal is below
  150.00.

All other rules of feature 001 are unchanged: a negative subtotal is rejected with an
`ArgumentOutOfRangeException`, and the total is rounded to 2 decimals, midpoint away from zero.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No order below 150.00 is discounted; every order of 150.00 or more is charged exactly 90 % of
  its subtotal.

## Assumptions

- The change applies to every order calculated after release; there is no transition period.
