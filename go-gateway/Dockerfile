FROM golang:1.22-bookworm AS builder

WORKDIR /app
COPY . .
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -o /go-gateway ./cmd/gateway

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

COPY --from=builder /go-gateway /usr/local/bin/go-gateway

EXPOSE 8091

CMD ["/usr/local/bin/go-gateway"]
