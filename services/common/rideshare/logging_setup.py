# Person 1. JSON logs on stdout so Fluent Bit can ship them.
#
# Each line has level, service, message, ride_id, event.
# configure() replaces the root handlers and returns a logger named SERVICE_NAME.
