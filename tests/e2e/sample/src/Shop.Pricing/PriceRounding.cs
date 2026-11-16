namespace Shop.Pricing;

/// <summary>Rounds money amounts to whole cents.</summary>
public static class PriceRounding
{
    /// <summary>The number of decimals of a money amount; the unit tests use it through InternalsVisibleTo.</summary>
    internal const int Decimals = 2;

    /// <summary>Rounds an amount to whole cents, halves to even.</summary>
    /// <param name="amount">The amount to round.</param>
    public static decimal ToCents(decimal amount) => Math.Round(amount, Decimals, MidpointRounding.ToEven);
}
