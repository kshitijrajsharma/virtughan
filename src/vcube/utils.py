import requests
from shapely.geometry import box, shape


def search_stac_api(bbox, start_date, end_date, cloud_cover, stac_api_url):
    search_params = {
        "collections": ["sentinel-2-l2a"],
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": cloud_cover}},
        "bbox": bbox,
        "limit": 100,
    }

    all_features = []
    next_link = None

    while True:
        response = requests.post(
            stac_api_url,
            json=search_params if not next_link else next_link["body"],
        )
        response.raise_for_status()
        response_json = response.json()

        all_features.extend(response_json["features"])

        next_link = next(
            (link for link in response_json["links"] if link["rel"] == "next"), None
        )
        if not next_link:
            break
    return all_features


def filter_features(features, bbox):
    bbox_polygon = box(bbox[0], bbox[1], bbox[2], bbox[3])
    return [
        feature
        for feature in features
        if shape(feature["geometry"]).contains(bbox_polygon)
    ]


def remove_overlapping_sentinel2_tiles(features):
    zone_counts = {}
    for feature in features:
        zone = feature["id"].split("_")[1][:2]
        zone_counts[zone] = zone_counts.get(zone, 0) + 1
    max_zone = max(zone_counts, key=zone_counts.get)

    filtered_features = {}
    for feature in features:
        parts = feature["id"].split("_")
        date = parts[2]
        zone = parts[1][:2]

        if zone == max_zone and date not in filtered_features:
            filtered_features[date] = feature

    return list(filtered_features.values())
