namespace Shop.Pricing;

/// <summary>Computes what a customer pays for an order.</summary>
public sealed class DiscountCalculator
{
    private const decimal Threshold = 150m;
    private const decimal DiscountFactor = 0.9m;

    /// <summary>Returns the total to pay for an order with the given subtotal.</summary>
    /// <param name="subtotal">The sum of the order lines, before any discount.</param>
    /// <exception cref="ArgumentOutOfRangeException">The subtotal is negative.</exception>
    public decimal Total(decimal subtotal)
    {
        ArgumentOutOfRangeException.ThrowIfNegative(subtotal);
        return subtotal >= Threshold
            ? Math.Round(subtotal * DiscountFactor, 2, MidpointRounding.AwayFromZero)
            : subtotal;
    }
}
