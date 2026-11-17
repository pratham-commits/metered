FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 65532 --create-home --shell /usr/sbin/nologin appuser
COPY services/common /tmp/common
COPY services/trip-tracking /app/service
RUN pip install --no-cache-dir -r /tmp/common/requirements.txt \
    && mkdir -p /app/rideshare \
    && cp -a /tmp/common/rideshare/. /app/rideshare/
ENV PYTHONPATH=/app
USER 65532
EXPOSE 8006
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8006"]
