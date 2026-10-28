// Person 3. Flink 1.20 job. EMR 7.14 runs it on YARN.
//
// Args: --bootstrap <brokers> --input ride-events --output demand-results.
// Set Kafka security.protocol=SSL on both the source and the sink. MSK is TLS on 9094.
// Watermarks: bounded out of order 10 seconds. Event time is payload event_time, UTC with a Z.
// Key by zone. Tumbling event-time window of 1 minute.
// Accumulator: set of rider ids for RIDE_REQUESTED, request count, assigned count,
// and the last DRIVER_STATUS per driver in the window.
// Emit JSON: zone, window_start, window_end, unique_riders, request_count, assigned_count,
// online_drivers, queue_length = max(0, requests - assigned),
// imbalance = requests / max(online_drivers, 1).
// Sink only to demand-results. Enable checkpointing every 60 seconds.
// RocksDB and the checkpoint directory are set on the EMR cluster, not in this class.
// Package with: mvn -q -DskipTests package
// Upload target/demand-analytics-1.0.0.jar to s3://<trip_bucket>/flink/demand-analytics.jar
