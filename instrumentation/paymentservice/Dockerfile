# Payment Service — Instrumented Build
# Based on the original Online Boutique paymentservice Dockerfile

FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --production

COPY . .

# OTel env vars — values injected via k8s deployment
ENV OTEL_EXPORTER_OTLP_ENDPOINT=""
ENV OTEL_SERVICE_NAME="paymentservice"
ENV OTEL_RESOURCE_ATTRIBUTES="service.version=1.0.0,deployment.environment=assessment"

EXPOSE 50051

# --require tracing.js loads OTel BEFORE the app code
# this is critical — auto-instrumentation patches modules at require() time
CMD ["node", "--require", "./tracing.js", "index.js"]
