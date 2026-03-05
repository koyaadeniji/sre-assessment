# Recommendation Service — Instrumented Build
# Based on the original Online Boutique recommendationservice Dockerfile

FROM python:3.12-slim

WORKDIR /app

# install deps first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# OTel env vars — actual endpoint set in k8s deployment
ENV OTEL_EXPORTER_OTLP_ENDPOINT=""
ENV OTEL_SERVICE_NAME="recommendationservice"
ENV OTEL_RESOURCE_ATTRIBUTES="service.version=1.0.0,deployment.environment=assessment"
ENV OTEL_PYTHON_LOG_CORRELATION="true"

EXPOSE 8080

# use opentelemetry-instrument wrapper for auto-instrumentation
# this catches anything we didn't manually instrument (HTTP clients, etc.)
ENTRYPOINT ["opentelemetry-instrument", "python", "recommendation_server.py"]
