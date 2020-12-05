import datetime
import logging
from json.decoder import JSONDecodeError
from urllib.parse import quote, urlparse

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


def get_post_response(endpoint, payload):
    logging.debug(f"Querying endpoint: {endpoint}")
    logging.debug(f"Payload: {payload}")

    post_request = requests.post(endpoint, json=payload)

    try:
        response_body = post_request.json()
    except JSONDecodeError:
        return post_request.text

    # return HTTP error code
    if not post_request.ok:
        msg = f"HTTP error {post_request.status_code}"
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


def get_search_payload(count, query, min_price, max_price, used_only, country):
    payload = {
        'count': count,
        'filters': [],
        'query': query,
        'sortParam': {
            'fieldName': 'time_created'
        }
    }

    price_dict = {
        'rangedFloat': {},
        'fieldName': 'price'
    }

    if min_price:
        price_dict['rangedFloat']['start'] = {'value': min_price}

    if max_price:
        price_dict['rangedFloat']['end'] = {'value': max_price}

    if price_dict['rangedFloat']:
        payload['filters'].append(price_dict)

    if used_only:
        used_dict = {
            'idsOrKeywords': {'value': ['USED']},
            'fieldName': 'condition_v2'
        }
        payload['filters'].append(used_dict)

    if country:
        payload['countryId'] = get_country_id(country)

    return payload


def get_listing(query, min_price=None, max_price=None, country=None, used_only=False, strict=False,
                count=FEED_ITEM_LIMIT):
    search_payload = get_search_payload(
        count, query, min_price, max_price, used_only, country)

    base_url = get_redirected_domain()
    search_endpoint = base_url + SEARCH_ENDPOINT

    response_body = get_post_response(search_endpoint, search_payload)

    parse_object = urlparse(base_url)
    domain = parse_object.netloc

    title_strings = [domain, f'Search results for "{query}"']

    term_list = []
    filters = []

    home_page_url_params = [
        f"search={quote(query)}", 'sort_by=time_created,descending']

    if min_price:
        filters.append(f"min {min_price}")
        home_page_url_params.append(f"price_start={min_price}")

    if max_price:
        filters.append(f"max {max_price}")
        home_page_url_params.append(f"price_end={max_price}")

    if used_only:
        filters.append('used only')
        home_page_url_params.append('condition_v2=USED')

    if strict:
        filters.append('strict')
        term_list = set([term.lower() for term in query.split()])
        if term_list:
            logging.debug(
                f"Strict mode enabled, title must contain: {term_list}")

    if filters:
        title_strings.append(f"Filtered by {', '.join(filters)}")

    output = {
        'version': JSONFEED_VERSION_URL,
        'title': ' - '.join(title_strings),
        'home_page_url': base_url + 'search/products/?' + '&'.join(home_page_url_params),
        'favicon': base_url + 'favicon.ico'
    }

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

        above_fold = get_flattened_fold(listing_card['aboveFold'])
        time_stamp_labels = ['time_created', 'expired_bump', 'active_bump']
        time_stamp_dict = {}

        for label in time_stamp_labels:
            try:
                if not time_stamp_dict:
                    time_stamp_dict = above_fold.get(label)
            except KeyError:
                logging.warning(
                    f"aboveFold.{label} not found, trying next label")
                continue

        time_stamp = time_stamp_dict['seconds']['low']

        item = {
            'id': item_url,
            'url': item_url,
            'title': f"[{item_price}] {item_title}",
            'content_text': item_desc,
            'date_published': datetime.datetime.utcfromtimestamp(time_stamp).isoformat('T'),
            'author': {
                'name': username
            }
        }

        if not strict or (term_list and all(item_title.lower().find(term) >= 0 for term in term_list)):
            items.append(item)
        else:
            logging.debug(f'Strict mode enabled, item "{item_title}" removed')

    output['items'] = items
    logging.debug(f"{len(items)} results published")

    return output
