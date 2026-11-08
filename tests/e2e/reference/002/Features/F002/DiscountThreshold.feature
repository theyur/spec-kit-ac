@F002
Feature: Raise the discount threshold

  @AC-001
  Scenario: A subtotal of exactly 150.00 gets 10 percent off
    Given an order with the subtotal 150.00
    When the total is calculated
    Then the total is 135.00

  @AC-002
  Scenario: A subtotal of 149.99 gets no discount
    Given an order with the subtotal 149.99
    When the total is calculated
    Then the total is 149.99

  @AC-003
  Scenario: A subtotal of 100.00 no longer gets a discount
    Given an order with the subtotal 100.00
    When the total is calculated
    Then the total is 100.00
