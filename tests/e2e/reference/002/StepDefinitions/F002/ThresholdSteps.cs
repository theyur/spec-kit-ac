using System.Globalization;
using Shop.Pricing;

namespace Shop.AcceptanceTests.StepDefinitions.F002;

[Binding, Scope(Tag = "F002")]
public sealed class ThresholdSteps
{
    private decimal _subtotal;
    private decimal? _total;
    private Exception? _error;

    [Given(@"an order with the subtotal (-?\d+\.\d+)")]
    public void GivenSubtotal(string subtotal) => _subtotal = decimal.Parse(subtotal, CultureInfo.InvariantCulture);

    [When("the total is calculated")]
    public void WhenCalculated()
    {
        try { _total = new DiscountCalculator().Total(_subtotal); }
        catch (Exception e) { _error = e; }
    }

    [Then(@"the total is (\d+\.\d+)")]
    public void ThenTotal(string expected)
    {
        Assert.Null(_error);
        Assert.Equal(decimal.Parse(expected, CultureInfo.InvariantCulture), _total);
    }
}
