from datetime import datetime
import logging
from json.decoder import JSONDecodeError
from urllib.parse import quote, urlparse
from search_query_class import SearchQueryClass

import requests


JSONFEED_VERSION_URL = 'https://jsonfeed.org/version/1'
FEED_ITEM_LIMIT = 20
SEARCH_ENDPOINT = 'api-service/filter/search/3.3/products/'
LISTING_ENDPOINT = 'api-service/listing/3.1/listings/'

country_to_geocode = {
    'AU': '2077456',
    'CA': '6251999',
    'ID': '1643084',
    'MY': '1733045',
    'NZ': '2186224',
    'PH': '1694008',
    'SG': '1880251',
    'TW': '1668284'
}

logging.basicConfig(level=logging.INFO)


def get_redirected_domain():
    request = requests.head('https://carousell.com', allow_redirects=True)
    return request.url


def get_country_id(country):
    return country_to_geocode.get(country)


def get_flattened_fold(fold_objects):
    keys = [list(string_obj.values())[0] for string_obj in fold_objects]
    # For 'belowFold' strings, relabel 'paragraph' keys by appending indices
    unique_keys = [key + str(index - 1) if key ==
                   'paragraph' else key for index, key in enumerate(keys)]
    values = [list(string_obj.values())[1] for string_obj in fold_objects]

    return dict(zip(unique_keys, values))


def get_response_body(response):
    try:
        response_body = response.json()
    except JSONDecodeError:
        return response.text

    # return HTTP error code
    if not response.ok:
        msg = f"HTTP error {response.status_code}"
        logging.error(msg)
        return msg

    # return API error message
    if response_body.get('error') is not None:
        msg = {
            'error': response_body.get('error').get('code'),
            'message': response_body.get('error').get('message')
        }
        logging.error(msg)
        return msg

    return response_body


def get_search_response(url, payload):
    logging.debug(f"Querying endpoint: {url}")
    logging.debug(f"Payload: {payload}")
    api_response = requests.post(url, json=payload)

    return get_response_body(api_response)


def get_listing_response(url, item_id):
    logging.debug(f"Querying endpoint: {url}/{item_id}")
    api_response = requests.post(url + '/' + item_id)

    return get_response_body(api_response)


def get_search_payload(search_query):
    payload = {
        'count': FEED_ITEM_LIMIT,
        'filters': [],
        'query': search_query.query,
        'sortParam': {
            'fieldName': 'time_created'
        }
    }

    price_dict = {
        'rangedFloat': {},
        'fieldName': 'price'
    }

    if search_query.min_price:
        price_dict['rangedFloat']['start'] = {'value': search_query.min_price}

    if search_query.max_price:
        price_dict['rangedFloat']['end'] = {'value': search_query.max_price}

    if price_dict['rangedFloat']:
        payload['filters'].append(price_dict)

    if search_query.used_only:
        used_dict = {
            'idsOrKeywords': {'value': ['USED']},
            'fieldName': 'condition_v2'
        }
        payload['filters'].append(used_dict)

    if search_query.country:
        payload['countryId'] = get_country_id(search_query.country)

    return payload


def get_top_level_feed(base_url, search_query):

    parse_object = urlparse(base_url)
    domain = parse_object.netloc

    title_strings = [domain, f'Search results for "{search_query.query}"']

    filters = []

    home_page_url_params = [
        f"search={quote(search_query.query)}", 'sort_by=time_created,descending']

    if search_query.min_price:
        filters.append(f"min {search_query.min_price}")
        home_page_url_params.append(f"price_start={search_query.min_price}")

    if search_query.max_price:
        filters.append(f"max {search_query.max_price}")
        home_page_url_params.append(f"price_end={search_query.max_price}")

    if search_query.used_only:
        filters.append('used only')
        home_page_url_params.append('condition_v2=USED')

    if search_query.strict:
        filters.append('strict')

    if filters:
        title_strings.append(f"Filtered by {', '.join(filters)}")

    output = {
        'version': JSONFEED_VERSION_URL,
        'title': ' - '.join(title_strings),
        'home_page_url': base_url + 'search/products/?' + '&'.join(home_page_url_params),
        'favicon': base_url + 'favicon.ico'
    }

    return output


def get_timestamp(base_url, listing_card):
    listing_url = base_url + LISTING_ENDPOINT

    item_id = listing_card['id']
    above_fold = get_flattened_fold(listing_card['aboveFold'])

    timestamp_labels = ['time_created', 'expired_bump', 'active_bump']
    timestamp_dict = {}

    for label in timestamp_labels:
        try:
            if not timestamp_dict:
                timestamp_dict = above_fold.get(label)
        except KeyError:
            logging.warning(
                f"aboveFold.{label} not found, trying next label")
            continue

    if timestamp_dict is None:
        listing_response = get_listing_response(listing_url, item_id)

        try:
            assert listing_response['data']
            datetime_obj = datetime.strptime(
                listing_response['data']['time_created'], '%Y-%m-%dT%H:%M:%SZ')
            timestamp = datetime_obj.timestamp()
        except KeyError:
            logging.warning(
                'Value time_created not found in listing ' + item_id)
            timestamp = datetime.now().timestamp()
    else:
        timestamp = timestamp_dict['seconds']['low']

    return timestamp


def get_listing(search_query):
    search_payload = get_search_payload(search_query)

    base_url = get_redirected_domain()
    search_url = base_url + SEARCH_ENDPOINT

    response_body = get_search_response(search_url, search_payload)
    output = get_top_level_feed(base_url, search_query)

    if search_query.strict:
        term_list = set([term.lower() for term in search_query.query.split()])
        logging.debug(f"Strict mode enabled, title must contain: {term_list}")

    try:
        assert response_body['data']['results']
        logging.debug(f"{len(response_body['data']['results'])} results found")
    except KeyError:
        msg = 'No results found.'
        logging.warning(msg)
        output['items'] = []
        return output

    items = []

    for result in response_body['data']['results']:
        listing_card = result['listingCard']
        username = listing_card['seller']['username']

        item_id = listing_card['id']
        item_url = base_url + f"p/{item_id}"

        below_fold = get_flattened_fold(listing_card['belowFold'])
        item_title = below_fold['header_1']
        item_price = below_fold['header_2']
        item_desc = below_fold['paragraph1']

        timestamp = get_timestamp(base_url, listing_card)

        item = {
            'id': item_url,
            'url': item_url,
            'title': f"[{item_price}] {item_title}",
            'content_text': item_desc,
            'date_published': datetime.utcfromtimestamp(timestamp).isoformat('T'),
            'author': {
                'name': username
            }
        }

        if not search_query.strict or (term_list and all(item_title.lower().find(term) >= 0 for term in term_list)):
            items.append(item)
        else:
            logging.debug(f'Strict mode enabled, item "{item_title}" removed')

    output['items'] = items
    logging.debug(f"{len(items)} results published")

    return output
