from collections import defaultdict

def remove_overlapping_landsat_tiles(features):
    """
    Remove overlapping Landsat tiles by selecting the best (least cloudy) per date and path/row.

    Parameters:
    features (list): STAC feature list.

    Returns:
    list: Filtered list with one best scene per date and path/row.
    """
    grouped = defaultdict(list)

    for feature in features:
        props = feature["properties"]
        date = props["datetime"].split("T")[0]
        path = props.get("landsat:wrs_path")
        row = props.get("landsat:wrs_row")
        key = f"{date}_{path}_{row}"
        grouped[key].append(feature)

    best_features = []
    for group in grouped.values():
        best = min(group, key=lambda f: f["properties"].get("eo:cloud_cover", 100))
        best_features.append(best)

    return best_features
