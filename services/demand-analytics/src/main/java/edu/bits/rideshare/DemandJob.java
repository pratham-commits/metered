package edu.bits.rideshare;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.common.functions.FilterFunction;
import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

import java.io.Serializable;
import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Properties;
import java.util.Set;

public class DemandJob {

    private static final ObjectMapper JSON = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        Config config = Config.parse(args);

        StreamExecutionEnvironment env =
                StreamExecutionEnvironment.getExecutionEnvironment();

        // Recover processing state after failures.
        env.enableCheckpointing(60_000);

        Properties kafkaProperties = new Properties();
        kafkaProperties.setProperty("security.protocol",
                System.getenv().getOrDefault("KAFKA_SECURITY_PROTOCOL", "SSL"));

        if (config.truststore != null) {
            kafkaProperties.setProperty(
                    "ssl.truststore.location", config.truststore);
            kafkaProperties.setProperty("ssl.truststore.type", "JKS");
        }

        String truststorePassword =
                System.getenv("KAFKA_TRUSTSTORE_PASSWORD");
        if (truststorePassword != null && !truststorePassword.isBlank()) {
            kafkaProperties.setProperty(
                    "ssl.truststore.password", truststorePassword);
        }

        KafkaSource<String> source = KafkaSource.<String>builder()
                .setBootstrapServers(config.bootstrap)
                .setTopics(config.input)
                .setGroupId("demand-analytics")
                .setStartingOffsets(OffsetsInitializer.earliest())
                .setValueOnlyDeserializer(new SimpleStringSchema())
                .setProperties(kafkaProperties)
                .build();

        DataStream<String> raw = env.fromSource(
                source,
                WatermarkStrategy.noWatermarks(),
                "ride-events-source"
        );

        DataStream<Event> events = raw
                .map(new ParseEvent())
                .filter(new RelevantEventFilter())
                .assignTimestampsAndWatermarks(
                        WatermarkStrategy
                                .<Event>forBoundedOutOfOrderness(
                                        Duration.ofSeconds(10))
                                .withTimestampAssigner(
                                        (event, previousTimestamp) ->
                                                event.eventTime
                                )
                );

        DataStream<String> results = events
                .keyBy(event -> event.zone)
                .window(TumblingEventTimeWindows.of(Time.minutes(1)))
                .aggregate(
                        new DemandAggregate(),
                        new DemandWindow()
                );

        KafkaSink<String> sink = KafkaSink.<String>builder()
                .setBootstrapServers(config.bootstrap)
                .setKafkaProducerConfig(kafkaProperties)
                .setRecordSerializer(
                        KafkaRecordSerializationSchema.builder()
                                .setTopic(config.output)
                                .setValueSerializationSchema(
                                        new SimpleStringSchema())
                                .build()
                )
                .setDeliveryGuarantee(DeliveryGuarantee.AT_LEAST_ONCE)
                .build();

        results.sinkTo(sink).name("demand-results-sink");

        env.execute("Ride Demand Analytics");
    }

    // CLI configuration
    private static class Config {
        String bootstrap;
        String input = "ride-events";
        String output = "demand-results";
        String truststore;

        static Config parse(String[] args) {
            Config config = new Config();

            for (int i = 0; i < args.length; i++) {
                if (i + 1 >= args.length) {
                    throw new IllegalArgumentException(
                            "Missing value for argument: " + args[i]);
                }

                String value = args[++i];

                switch (args[i - 1]) {
                    case "--bootstrap":
                        config.bootstrap = value;
                        break;
                    case "--input":
                        config.input = value;
                        break;
                    case "--output":
                        config.output = value;
                        break;
                    case "--truststore":
                        config.truststore = value;
                        break;
                    default:
                        throw new IllegalArgumentException(
                                "Unknown argument: " + args[i - 1]);
                }
            }

            if (config.bootstrap == null || config.bootstrap.isBlank()) {
                throw new IllegalArgumentException(
                        "Required argument: --bootstrap");
            }

            return config;
        }
    }

    // Kafka event representation
    public static class Event implements Serializable {
        public String eventType;
        public long eventTime;
        public String zone;
        public String rideId;
        public String riderId;
        public String driverId;
        public String status;
    }

    private static class ParseEvent implements MapFunction<String, Event> {
        @Override
        public Event map(String value) throws Exception {
            JsonNode node = JSON.readTree(value);

            Event event = new Event();
            event.eventType = text(node, "event_type");
            event.zone = text(node, "zone");
            event.rideId = text(node, "ride_id");
            event.riderId = text(node, "rider_id");
            event.driverId = text(node, "driver_id");

            String eventTime = text(node, "event_time");
            event.eventTime = Instant.parse(eventTime).toEpochMilli();

            JsonNode payload = node.path("payload");
            event.status = text(payload, "status");

            return event;
        }

        private static String text(JsonNode node, String field) {
            JsonNode value = node.path(field);
            return value.isMissingNode() || value.isNull()
                    ? ""
                    : value.asText();
        }
    }

    private static class RelevantEventFilter
            implements FilterFunction<Event> {
        @Override
        public boolean filter(Event event) {
            if (event.zone == null || event.zone.isBlank()) {
                return false;
            }

            return "RIDE_REQUESTED".equals(event.eventType)
                    || "RIDE_ASSIGNED".equals(event.eventType)
                    || "DRIVER_STATUS".equals(event.eventType);
        }
    }

    // Per-zone, per-window accumulator
    public static class DriverStatus implements Serializable {
        public long eventTime;
        public String status;

        DriverStatus(long eventTime, String status) {
            this.eventTime = eventTime;
            this.status = status;
        }
    }

    public static class DemandAccumulator implements Serializable {
        public Set<String> riders = new HashSet<>();
        public long requestCount = 0;
        public long assignedCount = 0;
        public Map<String, DriverStatus> drivers = new HashMap<>();
    }

    private static class DemandAggregate
            implements AggregateFunction<Event, DemandAccumulator,
                                          DemandAccumulator> {

        @Override
        public DemandAccumulator createAccumulator() {
            return new DemandAccumulator();
        }

        @Override
        public DemandAccumulator add(
                Event event, DemandAccumulator accumulator) {

            switch (event.eventType) {
                case "RIDE_REQUESTED":
                    accumulator.requestCount++;

                    if (event.riderId != null
                            && !event.riderId.isBlank()) {
                        accumulator.riders.add(event.riderId);
                    }
                    break;

                case "RIDE_ASSIGNED":
                    accumulator.assignedCount++;
                    break;

                case "DRIVER_STATUS":
                    if (event.driverId != null
                            && !event.driverId.isBlank()) {

                        DriverStatus previous =
                                accumulator.drivers.get(event.driverId);

                        // Retain the latest status by event time.
                        if (previous == null
                                || event.eventTime >= previous.eventTime) {
                            accumulator.drivers.put(
                                    event.driverId,
                                    new DriverStatus(
                                            event.eventTime, event.status)
                            );
                        }
                    }
                    break;

                default:
                    break;
            }

            return accumulator;
        }

        @Override
        public DemandAccumulator getResult(
                DemandAccumulator accumulator) {
            return accumulator;
        }

        @Override
        public DemandAccumulator merge(
                DemandAccumulator first,
                DemandAccumulator second) {

            first.riders.addAll(second.riders);
            first.requestCount += second.requestCount;
            first.assignedCount += second.assignedCount;

            for (Map.Entry<String, DriverStatus> entry
                    : second.drivers.entrySet()) {

                DriverStatus existing =
                        first.drivers.get(entry.getKey());
                DriverStatus candidate = entry.getValue();

                if (existing == null
                        || candidate.eventTime >= existing.eventTime) {
                    first.drivers.put(entry.getKey(), candidate);
                }
            }

            return first;
        }
    }

    // Window output
    private static class DemandWindow
            extends ProcessWindowFunction<
                    DemandAccumulator, String, String, TimeWindow> {

        @Override
        public void process(
                String zone,
                Context context,
                Iterable<DemandAccumulator> elements,
                Collector<String> out) throws Exception {

            DemandAccumulator accumulator = elements.iterator().next();

            long onlineDrivers = accumulator.drivers.values().stream()
                    .filter(driver -> "ONLINE".equalsIgnoreCase(
                            driver.status))
                    .count();

            long requests = accumulator.requestCount;
            long assigned = accumulator.assignedCount;

            long queueLength = Math.max(0, requests - assigned);
            double imbalance =
                    (double) requests / Math.max(onlineDrivers, 1);

            // Flink's window end is the last millisecond in the window.
            // Add one millisecond to emit the exclusive boundary.
            String windowStart = Instant.ofEpochMilli(
                    context.window().getStart()).toString();

            String windowEnd = Instant.ofEpochMilli(
                    context.window().getEnd() + 1).toString();

            Map<String, Object> result = new HashMap<>();
            result.put("zone", zone);
            result.put("window_start", windowStart);
            result.put("window_end", windowEnd);
            result.put("unique_riders", accumulator.riders.size());
            result.put("request_count", requests);
            result.put("assigned_count", assigned);
            result.put("online_drivers", onlineDrivers);
            result.put("queue_length", queueLength);
            result.put("imbalance", imbalance);

            out.collect(JSON.writeValueAsString(result));
        }
    }
}
