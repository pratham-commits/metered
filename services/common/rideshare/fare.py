# Person 1. Both Fare Lambda handlers import this. Do not fork the formula.
#
# quote_cents(distance_km, imbalance) -> (cents, surge, duration_min)
# base 4000 paise, 1200 per km, 200 per minute, speed 25 km/h.
# surge 2.0 if imbalance >= 3, else 1.5 if imbalance >= 1.5, else 1.0.
# quote_between(zone_a, zone_b, imbalance) uses zone centers and distance_km.
