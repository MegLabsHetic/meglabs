mod auth;
mod config;
mod engine;
mod error;
mod models;
mod quota;
mod routes;
mod state;
mod worker;

use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    dotenvy::dotenv().ok();

    let filter = std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into());
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(filter))
        .with(tracing_subscriber::fmt::layer())
        .init();

    let cfg = config::Config::from_env()?;

    let db = sqlx::postgres::PgPoolOptions::new()
        .max_connections(10)
        .connect(&cfg.database_url)
        .await?;

    sqlx::migrate!("./migrations").run(&db).await?;
    tracing::info!("migrations appliquees");

    let state = state::AppState {
        db,
        cfg: std::sync::Arc::new(cfg),
        http: reqwest::Client::new(),
    };

    // Worker de traitement des jobs en arriere-plan
    worker::spawn(state.clone());

    let app = routes::router(state.clone());
    let listener = tokio::net::TcpListener::bind(&state.cfg.bind_addr).await?;
    tracing::info!("API en ecoute sur {}", state.cfg.bind_addr);
    axum::serve(listener, app).await?;
    Ok(())
}
