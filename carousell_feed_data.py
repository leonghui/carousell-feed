from dataclasses import dataclass, field


@dataclass
class Country():
    code: str
    geocode: str
    domain: str


country_data = [
    Country('AU', '2077456', 'au.carousell.com'),
    Country('CA', '6251999', 'ca.carousell.com'),
    Country('HK', '1819730', 'www.carousell.com.hk'),
    Country('ID', '1643084', 'id.carousell.com'),
    Country('MY', '1733045', 'www.carousell.com.my'),
    Country('NZ', '2186224', 'nz.carousell.com'),
    Country('PH', '1694008', 'www.carousell.ph'),
    Country('TW', '1668284', 'tw.carousell.com')
]

DEFAULT_COUNTRY = Country('SG', '1880251', 'www.carousell.sg')
country_data.append(DEFAULT_COUNTRY)


def string_to_boolean(string):
    return string.lower().strip() in ['yes', 'true']


@dataclass
class QueryStatus():
    ok: bool = True
    errors: list[str] = field(default_factory=list)

    def refresh(self):
        self.ok = False if self.errors else True


def get_matching_country(country):
    return next((country_obj for country_obj in country_data if country.upper() == country_obj.code), DEFAULT_COUNTRY)


@dataclass
class _BaseQuery():
    query: str
    status: QueryStatus
    country: str = None
    country_obj: Country = None

    def validate_country(self):
        if not self.country:
            self.country = DEFAULT_COUNTRY.code
        if len(self.country) != 2:
            self.status.errors.append('Invalid country')
        self.country_obj = get_matching_country(self.country)


@dataclass
class _PriceFilter():
    min_price: str = None
    max_price: str = None


@dataclass
class _BaseQueryWithPriceFilter(_PriceFilter, _BaseQuery):
    def validate_price_filters(self):
        if self.max_price and not self.max_price.isnumeric():
            self.status.errors.append('Invalid max price')

        if self.min_price and not self.min_price.isnumeric():
            self.status.errors.append('Invalid min price')


@dataclass
class _CarousellSearchFilter:
    used_only: bool = False
    strict: bool = False

    def validate_carousell_search_filters(self):
        if self.used_only:
            self.used_only = string_to_boolean(self.used_only)
        if self.strict:
            self.strict = string_to_boolean(self.strict)


@dataclass
class CarousellSearchQuery(_CarousellSearchFilter, _BaseQueryWithPriceFilter):
    __slots__ = ['query', 'country', 'min_price',
                 'max_price', 'used_only', 'strict']

    def __post_init__(self):
        if not isinstance(self.query, str):
            self.status.errors.append('Invalid query')

        self.validate_country()
        self.validate_price_filters()
        self.validate_carousell_search_filters()
        self.status.refresh()
