using Xunit;

namespace Shop.Pricing.Tests;

public class DiscountCalculatorTests
{
    [Fact]
    public void CanBeCreated() => Assert.NotNull(new DiscountCalculator());
}
