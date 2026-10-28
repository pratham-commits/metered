# Person 1. The demo city grid.
#
# Bounds: lat 17.30-17.50, lng 78.30-78.50, 4 rows by 4 columns.
# Zone ids z00 through z33. zone_for(lat, lng) clamps into the box.
# center(zone) -> (lat, lng) of the cell center.
# neighbors(zone) includes the zone itself and the adjacent cells.
# all_zones() -> the 16 ids.
# distance_km(lat1, lng1, lat2, lng2) haversine, Earth radius 6371.
