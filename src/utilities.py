import urllib.parse


def create_search_link(query: str, lang=None, geo_coordinates=None, zoom=None):
    """Build a Google Maps search URL for one user-supplied query."""
    if geo_coordinates is None and zoom is not None:
        raise ValueError("geo_coordinates must be provided along with zoom")

    params = {"authuser": "0", "entry": "ttu"}
    if lang is not None:
        params["hl"] = lang

    endpoint = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/maps/search/{endpoint}"
    if geo_coordinates is not None:
        geo_coordinates = geo_coordinates.replace(" ", "")
        geo_str = f"/@{geo_coordinates}"
        if zoom is not None:
            geo_str += f",{zoom}z"
        url += geo_str
    return f"{url}?{urllib.parse.urlencode(params)}"