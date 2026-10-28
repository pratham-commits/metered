# Person 1. The trace-page writer.
#
# record_hop(conn, ride_id, service, mechanism, store, detail)
# Inserts into ride_hops. mechanism is REST, GRPC, QUEUE, or EVENT.
# store is SQL, NOSQL, OBJECT, or NONE. detail is stored as jsonb.
# No-op when ride_id is empty.
