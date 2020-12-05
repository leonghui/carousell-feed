from dataclasses import dataclass


@dataclass
class SearchQueryClass:
    query: str
    min_price: str = None
    max_price: str = None
    country: str = None
    used_only: bool = False
    strict: bool = False
