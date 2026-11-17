FROM python:3.12-slim
WORKDIR /app
COPY services/common /tmp/common
COPY services/fare /app/service
RUN pip install --no-cache-dir -r /tmp/common/requirements.txt \
    && pip install --no-cache-dir -r /app/service/requirements.txt
ENV PYTHONPATH=/tmp/common:/app/service
EXPOSE 8007
CMD ["functions-framework", "--source", "/app/service/handler.py", "--target", "estimate", "--host", "0.0.0.0", "--port", "8007"]
