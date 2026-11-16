using Xunit;

namespace Shop.Pricing.Tests;

public class PriceRoundingTests
{
    [Fact]
    public void RoundsToTheInternalNumberOfDecimals() =>
        Assert.Equal(decimal.Round(1.005m, PriceRounding.Decimals, MidpointRounding.ToEven), PriceRounding.ToCents(1.005m));
}
