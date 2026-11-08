# Acceptance criteria: Order discount

**Feature**: specs/001-order-discount · **Tag**: F001 · **Spec**: spec.md

## Coverage

| Requirement / scenario | AC items | Note |
|---|---|---|
| FR-001 | AC-001, AC-002 | |
| FR-002 | AC-003 | |
| FR-003 | AC-004 | |
| FR-004 | AC-005 | |
| US1-AS1 | AC-001, AC-002 | |
| US1-AS2 | AC-003 | |
| US1-AS3 | AC-005 | |
| US2-AS1 | AC-004 | |

## Acceptance criteria

### AC-001 (FR-001; US1-AS1) A subtotal of exactly 100.00 gets 10 percent off

- Given an order with the subtotal 100.00
- When the total is calculated
- Then the total is 90.00

### AC-002 (FR-001; US1-AS1) A subtotal of 200.00 gets 10 percent off

- Given an order with the subtotal 200.00
- When the total is calculated
- Then the total is 180.00

### AC-003 (FR-002; US1-AS2) A subtotal of 99.99 gets no discount

- Given an order with the subtotal 99.99
- When the total is calculated
- Then the total is 99.99

### AC-004 (FR-003; US2-AS1) A negative subtotal is rejected

- Given an order with the subtotal -0.01
- When the total is calculated
- Then the subtotal is rejected

### AC-005 (FR-004; US1-AS3) The discounted total is rounded half away from zero

- Given an order with the subtotal 123.45
- When the total is calculated
- Then the total is 111.11
