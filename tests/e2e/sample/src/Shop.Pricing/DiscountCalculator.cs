namespace Shop.Pricing;

/// <summary>Computes what a customer pays for an order.</summary>
public sealed class DiscountCalculator
{
    /// <summary>Returns the total to pay for an order with the given subtotal.</summary>
    /// <param name="subtotal">The sum of the order lines, before any discount.</param>
    public decimal Total(decimal subtotal) => throw new NotImplementedException();
}
