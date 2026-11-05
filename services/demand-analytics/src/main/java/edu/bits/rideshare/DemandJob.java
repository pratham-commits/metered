// Person 3. Flink 1.20 job. Dataproc 2.2 with the FLINK component runs it.
//
// Args: --bootstrap <brokers> --input ride-events --output demand-results
//       [--truststore /opt/kafka/kafka.truststore.jks]
// Set Kafka security.protocol=SSL on both the source and the sink. Strimzi's
// internal/external listeners are TLS on 9094/9095. Dataproc uses the external
// listener (9095) and the JKS truststore staged by scripts/bootstrap-gcp.sh.
// Watermarks: bounded out of order 10 seconds. Event time is payload event_time, UTC with a Z.
// Key by zone (the H3 cell string). Tumbling event-time window of 1 minute.
// Accumulator: set of rider ids for RIDE_REQUESTED, request count, assigned count,
// and the last DRIVER_STATUS per driver in the window.
// Emit JSON: zone, window_start, window_end, unique_riders, request_count, assigned_count,
// online_drivers, queue_length = max(0, requests - assigned),
// imbalance = requests / max(online_drivers, 1).
// Sink only to demand-results. Enable checkpointing every 60 seconds.
// Package with: mvn -q -DskipTests package
// Upload target/demand-analytics-1.0.0.jar to gs://<trip_bucket>/flink/demand-analytics.jar
