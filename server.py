from flask import Flask, request, jsonify, abort
from flask.logging import create_logger

from carousell_feed import get_search_results
from carousell_feed_data import CarousellSearchQuery, QueryStatus


app = Flask(__name__)
app.config.update({'JSONIFY_MIMETYPE': 'application/feed+json'})
logger = create_logger(app)


def generate_response(query_object):
    if not query_object.status.ok:
        abort(400, description='Errors found: ' +
              ', '.join(query_object.status.errors))

    logger.debug(query_object)  # log values

    output = get_search_results(query_object, logger)
    return jsonify(output)


@app.route('/', methods=['GET'])
@app.route('/search', methods=['GET'])
def process_query():
    query = request.args.get('query')
    country = request.args.get('country')
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    used_only = request.args.get('used_only')
    strict = request.args.get('strict')

    search_query = CarousellSearchQuery(
        query=query,
        min_price=min_price,
        max_price=max_price,
        country=country,
        used_only=used_only,
        strict=strict,
        status=QueryStatus()
    )

    return generate_response(search_query)


if __name__ == '__main__':
    app.run(host='0.0.0.0', use_reloader=False)
