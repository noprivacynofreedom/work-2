FROM rust:1.83-bookworm AS build
WORKDIR /app
COPY Cargo.toml ./
COPY migrations ./migrations
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
RUN useradd --system --uid 10001 atlas && apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /app/target/release/atlas-control-plane /usr/local/bin/atlas-control-plane
USER atlas
EXPOSE 8181
ENTRYPOINT ["/usr/local/bin/atlas-control-plane"]
