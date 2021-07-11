# carousell-feed
A simple Python script to generate a [JSON Feed](https://github.com/brentsimmons/JSONFeed) for search results on [Carousell](https://www.carousell.com).

Uses the unofficial API and served over [Flask!](https://github.com/pallets/flask/)

Use the [Docker build](https://github.com/users/leonghui/packages/container/package/carousell-feed) to host your own instance.

1. Set your timezone as an environment variable (see [docker docs]): `TZ=America/Los_Angeles`

2. Access the feed using the URL: `http://<host>/?query={query_string}&country={AU/CA/ID/MY/NZ/PH/SG/TW}`

3. Optionally, filter by:
    - country: `http://<host>/?query={query_string}&country={AU/CA/ID/MY/NZ/PH/SG/TW}`
    - max price: `http://<host>/?query={query_string}&max_price={int}&country={AU/CA/ID/MY/NZ/PH/SG/TW}`
    - min price: `http://<host>/?query={query_string}&min_price={int}&country={AU/CA/ID/MY/NZ/PH/SG/TW}`
    - used items only: `http://<host>/?query={query_string}&used_only=yes&country={AU/CA/ID/MY/NZ/PH/SG/TW}`
    - strict mode (terms must appear in the title): `http://<host>/?query={query_string}&strict=yes&country={AU/CA/ID/MY/NZ/PH/SG/TW}`

E.g.
```
Search results for used "nintendo switch" in Singapore between $200 to $250:
https://sg.carousell.com/search/products/?search=nintendo%20switch&condition_v2=USED&price_end=250&price_start=200&sort_by=time_created%2Cdescending

Feed link:
http://<host>/?query=nintendo%20switch&min_price=200&max_price=250&country=SG&used_only=true&strict=true
```

Tested with:
- [Nextcloud News App](https://github.com/nextcloud/news)

[docker docs]:(https://docs.docker.com/compose/environment-variables/#set-environment-variables-in-containers)
