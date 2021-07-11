from dataclasses import dataclass, field
from typing import List

JSONFEED_VERSION_URL = 'https://jsonfeed.org/version/1.1'


@dataclass
class JsonFeedAuthor():
    name: str = None
    url: str = None
    avatar: str = None


@dataclass
class JsonFeedItem():
    authors: List[JsonFeedAuthor]
    id: str  # required
    url: str = None
    title: str = None
    content_html: str = None
    image: str = None
    date_published: str = None
    author: JsonFeedAuthor = None  # deprecated


@dataclass
class JsonFeedTopLevel():
    authors: List[JsonFeedAuthor]
    title: str  # required
    items: List[JsonFeedItem]  # required
    version: str = JSONFEED_VERSION_URL  # required
    home_page_url: str = None
    description: str = None
    favicon: str = None
    author: JsonFeedAuthor = None  # deprecated
