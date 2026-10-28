# Person 3. Copies demand-results into rideshare_demand_windows. Port 8010.
#
# install(app, "demand-sink") with no database readiness check.
# A daemon thread consumes KAFKA_TOPIC_RESULTS, group demand-sink, from earliest.
# On each record, put_demand with zone, window_start, window_end, unique_riders,
# request_count, assigned_count, online_drivers, queue_length, imbalance, topic.
# If the topic does not exist yet, catch the error, sleep 5 seconds, and try again.
# The thread must stay alive until the topic appears.
