# Shop

A small .NET 10 class library, `Shop.Pricing`, that computes what a customer pays for an order.
Features are specified with spec-kit (`specs/NNN-name/`).

- Build: `dotnet build Shop.slnx`
- Unit tests: `dotnet test tests/Shop.Pricing.Tests/Shop.Pricing.Tests.csproj`
- Money is `decimal`, always; never `double`.
