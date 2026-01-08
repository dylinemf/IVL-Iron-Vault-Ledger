from enum import Enum

class SupportedCountry(str, Enum):
    """ISO 3166-1 alpha-2 country codes for supported regions."""
    CH = "CH"  # Switzerland
    DE = "DE"  # Germany
    AT = "AT"  # Austria
    FR = "FR"  # France
    US = "US"  # United States

class SupportedCurrency(str, Enum):
    """Supported currencies."""
    CHF = "CHF"
    EUR = "EUR"
    USD = "USD"

COUNTRY_CURRENCY_MAP = {
    SupportedCountry.CH: SupportedCurrency.CHF,
    SupportedCountry.DE: SupportedCurrency.EUR,
    SupportedCountry.AT: SupportedCurrency.EUR,
    SupportedCountry.FR: SupportedCurrency.EUR,
    SupportedCountry.US: SupportedCurrency.USD,
}
