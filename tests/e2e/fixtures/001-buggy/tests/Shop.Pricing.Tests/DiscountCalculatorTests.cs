using Xunit;

namespace Shop.Pricing.Tests;

public class DiscountCalculatorTests
{
    [Fact]
    public void SmallOrderIsNotDiscounted() => Assert.Equal(50.00m, new DiscountCalculator().Total(50.00m));

    [Fact]
    public void LargeOrderGetsTenPercentOff() => Assert.Equal(180.00m, new DiscountCalculator().Total(200.00m));
}
