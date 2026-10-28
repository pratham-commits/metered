# Person 1. Shared FastAPI setup.
#
# install(app, service_name, ready_check=None) sets SERVICE_NAME,
# adds HTTP middleware that records http_requests_total and http_request_duration_seconds
# with labels service, method, path, status. Path is the route template.
# GET /healthz returns {ok, service}. GET /readyz calls ready_check when given.
# Mount /metrics from prometheus_client.
