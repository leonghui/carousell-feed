from flask import Flask, request, jsonify
from requests import exceptions

from carousell_feed import get_listing

app = Flask(__name__)


def string_to_boolean(string):
    return string.lower().strip() in ['yes', 'true']


@app.route('/', methods=['GET'])
def form():
    query = request.args.get('query')
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    country_text = request.args.get('country')
    used_only_text = request.args.get('used_only')
    strict_text = request.args.get('strict')

    if not isinstance(query, str):
        return 'Please provide a valid query string.'

    if min_price and not min_price.isnumeric():
        return 'Invalid min price.'

    if max_price and not max_price.isnumeric():
        return 'Invalid max price.'

    country = False

    if country_text:
        if isinstance(country_text, str) and len(country_text) == 2:
            country = country_text.upper()
        else:
            return 'Please provide a valid country code.'

    used_only = True if isinstance(used_only_text, str) and string_to_boolean(used_only_text) else False

    strict = True if isinstance(strict_text, str) and string_to_boolean(strict_text) else False

    try:
        output = get_listing(query, min_price, max_price, country, used_only, strict)
        return jsonify(output)
    except exceptions.RequestException:
        return f"Error generating output for query {query}."


if __name__ == '__main__':
    app.run(host='0.0.0.0')
