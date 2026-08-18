# ── Etape de build ──────────────────────────────
FROM rust:slim AS build
WORKDIR /app
# build-essential fournit le compilateur C requis par ring (rustls)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 1) Compile d'abord les dependances seules (couche cachee tant que Cargo.toml ne change pas)
COPY Cargo.toml ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release && rm -rf src

# 2) Puis le code : on invalide l'artefact factice pour forcer la recompilation
#    du vrai crate (les dependances dans deps/ restent cachees).
COPY src ./src
COPY migrations ./migrations
RUN rm -f target/release/api target/release/deps/api-* && cargo build --release

# ── Image finale ────────────────────────────────
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /app/target/release/api /usr/local/bin/api
COPY migrations ./migrations
ENV BIND_ADDR=0.0.0.0:8080
EXPOSE 8080
CMD ["api"]
