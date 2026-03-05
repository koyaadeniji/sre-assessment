# Frontend Service — Instrumented Build
# Based on the original Online Boutique frontend Dockerfile
# with OpenTelemetry Go SDK dependencies added

FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git ca-certificates

WORKDIR /src

# copy go mod files first for better layer caching
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# build with OTel deps included
RUN CGO_ENABLED=0 GOOS=linux go build -o /frontend ./main.go

# --- runtime image ---
FROM alpine:3.19
RUN apk add --no-cache ca-certificates

WORKDIR /app
COPY --from=builder /frontend .
COPY ./templates ./templates
COPY ./static ./static

# OTel SDK reads these env vars to know where to send telemetry
# the actual values come from the k8s deployment manifest
ENV OTEL_EXPORTER_OTLP_ENDPOINT=""
ENV OTEL_SERVICE_NAME="frontend"
ENV OTEL_RESOURCE_ATTRIBUTES="service.version=1.0.0,deployment.environment=assessment"

EXPOSE 8080
ENTRYPOINT ["/app/frontend"]
