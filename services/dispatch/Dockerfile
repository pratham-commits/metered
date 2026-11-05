# Person 2. Same image pattern as services/rider/Dockerfile.
# COPY services/dispatch. EXPOSE 8005 and 9005. uvicorn on port 8005.

FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 65532 --create-home --shell /usr/sbin/nologin appuser
COPY proto /proto
COPY services/common /tmp/common
COPY services/dispatch /app/service
RUN pip install --no-cache-dir -r /tmp/common/requirements.txt \
 && python -m grpc_tools.protoc -I /proto --python_out=/app --grpc_python_out=/app \
      /proto/ride/v1/driver.proto /proto/ride/v1/dispatch.proto \
 && mkdir -p /app/ride/v1 \
 && touch /app/ride/__init__.py /app/ride/v1/__init__.py \
 && cp -a /tmp/common/rideshare /app/rideshare
ENV PYTHONPATH=/app
USER 65532
EXPOSE 8005 9005
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8005"]