from datetime import datetime
from urllib.parse import quote, urlparse, urlencode
from flask import abort
from requests import Session
from dataclasses import asdict
from time import sleep

import bleach

from carousell_feed_data import CarousellSearchQuery
from json_feed_data import JsonFeedTopLevel, JsonFeedItem, JsonFeedAuthor


FEED_ITEM_LIMIT = 22
SEARCH_ENDPOINT = 'api-service/filter/search/3.3/products/'
LISTING_ENDPOINT = 'api-service/listing/3.1/listings/'

allowed_tags = bleach.ALLOWED_TAGS + ['img', 'p']
allowed_attributes = bleach.ALLOWED_ATTRIBUTES.copy()
allowed_attributes.update({'img': ['src']})

session = Session()


# modified from https://stackoverflow.com/a/24893252
def remove_empty_from_dict(d):
    if isinstance(d, dict):
        return dict((k, remove_empty_from_dict(v)) for k, v in d.items() if v and remove_empty_from_dict(v))
    elif isinstance(d, list):
        return [remove_empty_from_dict(v) for v in d if v and remove_empty_from_dict(v)]
    else:
        return d


def get_flattened_fold(fold_objects):
    keys = [list(string_obj.values())[0] for string_obj in fold_objects]
    # For 'belowFold' strings, relabel 'paragraph' keys by appending indices
    unique_keys = [key + str(index - 1) if key ==
                   'paragraph' else key for index, key in enumerate(keys)]
    values = [list(string_obj.values())[1] for string_obj in fold_objects]

    return dict(zip(unique_keys, values))


def get_search_payload(search_query, logger):
    payload = {
        'count': FEED_ITEM_LIMIT,
        'countryCode': search_query.country_obj.code,   # appears to be optional
        'countryId': search_query.country_obj.geocode,
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

    return payload


def process_response(response, query_object, logger):

    # return HTTP error code
    if not response.ok:
        logger.debug(
            f'"{query_object.query}" - error from source, dumping input:')
        logger.debug(response.text)
        abort(
            500, description='HTTP status from source: ' + response.status_code)

    try:
        return response.json()
    except ValueError:
        logger.debug(
            f'"{query_object.query}" - invalid API response, dumping input:')
        logger.debug(response.text)
        abort(
            500, description='Invalid API response')


def get_search_response(base_url, query_object, logger):

    search_url = base_url + SEARCH_ENDPOINT

    payload = get_search_payload(query_object, logger)

    logger.debug(f'"{query_object.query}" - querying endpoint: {search_url}')
    logger.debug(f'"{query_object.query}" - payload: {payload}')
    response = session.post(search_url, json=payload)

    return process_response(response, query_object, logger)


def get_listing_response(base_url, item_id, query_object, logger):

    listing_url = base_url + LISTING_ENDPOINT

    logger.debug(
        f'"{query_object.query}" - querying endpoint: {listing_url}{item_id}')
    response = session.get(listing_url + item_id)
    sleep(1)

    return process_response(response, query_object, logger)


def get_top_level_feed(base_url, query_object):

    parse_object = urlparse(base_url)
    domain = parse_object.netloc

    title_strings = [domain, query_object.query]

    filters = []

    search_params_dict = {
        'search': quote(query_object.query),
        'sort_by': 'time_created,descending'
    }

    if query_object.min_price:
        filters.append(f"min {query_object.min_price}")
        search_params_dict['price_start'] = query_object.min_price

    if query_object.max_price:
        filters.append(f"max {query_object.max_price}")
        search_params_dict['price_end'] = query_object.max_price

    if query_object.used_only:
        filters.append('used only')
        search_params_dict['condition_v2'] = 'USED'

    if query_object.strict:
        filters.append('strict')

    if filters:
        title_strings.append(f"Filtered by {', '.join(filters)}")

    json_feed = JsonFeedTopLevel(
        items=[],
        title=' - '.join(title_strings),
        home_page_url=base_url + 'search/products/?' +
        urlencode(search_params_dict),
        favicon=base_url + 'favicon.ico'
    )

    return json_feed


def get_timestamp(base_url, listing_card, query_obj, logger):
    # attempt to extract timestamp (in Unix time) from search result
    # if unavailable, extract timestamp (in str) from item listing

    TIME_CREATED_KEY = 'time_created'

    try:
        item_id = listing_card['id']
        above_fold = get_flattened_fold(listing_card['aboveFold'])
        timestamp_dict = above_fold.get(TIME_CREATED_KEY)

        if timestamp_dict:
            return timestamp_dict['seconds']['low']
        else:
            logger.info(
                f'"{query_obj.query}" - {TIME_CREATED_KEY} not found for item {item_id}')
            response_json = get_listing_response(
                base_url, item_id, query_obj, logger)
            datetime_obj = datetime.strptime(
                response_json['data'][TIME_CREATED_KEY], '%Y-%m-%dT%H:%M:%SZ')
            return datetime_obj.timestamp()
    except KeyError:
        logger.info(
            f'"{query_obj.query}" - using default timestamp for item {item_id}')
        return datetime.now().timestamp()


def get_thumbnail(listing_card):
    try:
        return listing_card['photoUrls'][0]
    except KeyError:
        return None


def get_search_results(search_query, logger):

    base_url = 'https://' + search_query.country_obj.domain + '/'

    response_json = get_search_response(base_url, search_query, logger)

    if search_query.strict:
        term_list = set([term.lower() for term in search_query.query.split()])
        logger.debug(
            f'"{search_query.query}" - strict mode enabled, title must contain: {term_list}')

    json_feed = get_top_level_feed(base_url, search_query)

    data_json = response_json.get('data')
    results = data_json.get('results')

    if results:
        for result in results:
            listing_card = result.get('listingCard')
            username = listing_card.get('seller').get('username')

            item_id = listing_card.get('id')
            item_url = base_url + 'p/' + item_id

            below_fold = get_flattened_fold(listing_card.get('belowFold'))
            item_title = below_fold.get('header_1')
            item_price = below_fold.get('header_2')
            item_desc = below_fold.get('paragraph1')

            timestamp = get_timestamp(
                base_url, listing_card, search_query, logger)
            thumbnail_url = get_thumbnail(listing_card)

            content_body = f'<img src=\"{thumbnail_url}\" /><p>{item_desc}</p>'

            feed_item = JsonFeedItem(
                id=item_url,
                url=item_url,
                title=f"[{item_price}] {item_title}",
                content_html=bleach.clean(
                    content_body,
                    tags=allowed_tags,
                    attributes=allowed_attributes
                ),
                date_published=datetime.utcfromtimestamp(
                    timestamp).isoformat('T'),
                author=JsonFeedAuthor(name=username)
            )

            if thumbnail_url:
                feed_item.image = thumbnail_url

            if search_query.strict and (term_list and not all(item_title.lower().find(term) >= 0 for term in term_list)):
                logger.debug(
                    f'"{search_query.query}" - strict mode - removed {item_id} "{item_title}"')
            else:
                json_feed.items.append(feed_item)

        logger.info(
            f'"{search_query.query}" - found {len(results)} - published {len(json_feed.items)}')

    return remove_empty_from_dict(asdict(json_feed))
