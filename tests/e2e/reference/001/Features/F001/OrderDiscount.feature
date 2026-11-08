@F001
Feature: Order discount

  @AC-001
  Scenario: A subtotal of exactly 100.00 gets 10 percent off
    Given an order with the subtotal 100.00
    When the total is calculated
    Then the total is 90.00

  @AC-002
  Scenario: A subtotal of 200.00 gets 10 percent off
    Given an order with the subtotal 200.00
    When the total is calculated
    Then the total is 180.00

  @AC-003
  Scenario: A subtotal of 99.99 gets no discount
    Given an order with the subtotal 99.99
    When the total is calculated
    Then the total is 99.99

  @AC-004
  Scenario: A negative subtotal is rejected
    Given an order with the subtotal -0.01
    When the total is calculated
    Then the subtotal is rejected

  @AC-005
  Scenario: The discounted total is rounded half away from zero
    Given an order with the subtotal 123.45
    When the total is calculated
    Then the total is 111.11
