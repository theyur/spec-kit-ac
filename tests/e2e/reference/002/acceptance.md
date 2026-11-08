# Acceptance criteria: Raise the discount threshold

**Feature**: specs/002-raise-discount-threshold · **Tag**: F002 · **Spec**: spec.md

## Coverage

| Requirement / scenario | AC items | Note |
|---|---|---|
| FR-001 | AC-001 | |
| FR-002 | AC-002, AC-003 | |
| US1-AS1 | AC-001 | |
| US1-AS2 | AC-002, AC-003 | |

## Acceptance criteria

### AC-001 (FR-001; US1-AS1) A subtotal of exactly 150.00 gets 10 percent off

- Given an order with the subtotal 150.00
- When the total is calculated
- Then the total is 135.00

### AC-002 (FR-002; US1-AS2) A subtotal of 149.99 gets no discount

- Given an order with the subtotal 149.99
- When the total is calculated
- Then the total is 149.99

### AC-003 (FR-002; US1-AS2) A subtotal of 100.00 no longer gets a discount

- Given an order with the subtotal 100.00
- When the total is calculated
- Then the total is 100.00
