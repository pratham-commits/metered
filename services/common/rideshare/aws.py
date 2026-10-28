# Person 1. The only module that calls boto3 or kafka-python.
#
# get_store() returns a process-wide Store.
# Clients use AWS_REGION and, when set, AWS_ENDPOINT_URL (LocalStack).
# put_driver(item) writes rideshare_driver_live.
# query_available(partition_id, zones) returns AVAILABLE drivers in those zones.
# assign(partition_id, driver_id, ride_id) conditional update:
#   succeed when status is AVAILABLE, or when it is already ASSIGNED to this same ride_id.
#   return False on ConditionalCheckFailedException.
# release(partition_id, driver_id) sets AVAILABLE and clears assigned_ride_id.
# put_object, send_job, receive_jobs (long poll 20s, visibility 60), delete_job.
# latest_demand(zone) and latest_all() read rideshare_demand_windows, newest first.
# put_demand(item) writes every value as a string.
# publish(event) sends to KAFKA_TOPIC_EVENTS. publish_topic(topic, event) for the sink side.
# Kafka security protocol comes from KAFKA_SECURITY_PROTOCOL (SSL on AWS, PLAINTEXT locally).
# A Kafka failure is logged and returns False. It must not fail the rider or driver request.
