def remove_overlapping_sentinel2_tiles(features):
    """
    Remove overlapping Sentinel-2 tiles.

    Parameters:
    features (list): List of features to process.

    Returns:
    list: List of non-overlapping features.
    """
    if not features:
        return []

    zone_counts = {}
    for feature in features:
        zone = feature["id"].split("_")[1][:2]
        zone_counts[zone] = zone_counts.get(zone, 0) + 1

    if not zone_counts:
        return []

    max_zone = max(zone_counts, key=zone_counts.get)

    filtered_features = {}
    for feature in features:
        parts = feature["id"].split("_")
        date = parts[2]
        zone = parts[1][:2]

        if zone == max_zone and date not in filtered_features:
            filtered_features[date] = feature

    return list(filtered_features.values())