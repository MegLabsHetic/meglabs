use uuid::Uuid;

use crate::{config::tier_limits, error::ApiError, state::AppState};

/// Refuse l'action si le quota journalier du palier est atteint.
pub async fn enforce(state: &AppState, user_id: Uuid, action: &str) -> Result<(), ApiError> {
    let tier: String = sqlx::query_scalar("SELECT tier FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_one(&state.db)
        .await?;

    let (uploads, ai) = tier_limits(&tier);
    let limit = match action {
        "upload" => uploads,
        "ai_query" => ai,
        _ => -1,
    };
    if limit < 0 {
        return Ok(());
    }

    let used: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM usage_events \
         WHERE user_id = $1 AND action = $2 AND created_at::date = now()::date",
    )
    .bind(user_id)
    .bind(action)
    .fetch_one(&state.db)
    .await?;

    if used >= limit {
        return Err(ApiError::TooManyRequests(format!(
            "Limite journaliere atteinte pour '{action}' ({limit}/jour). Passez a un palier superieur."
        )));
    }
    Ok(())
}

/// Enregistre un evenement d'usage (best-effort).
pub async fn log(state: &AppState, user_id: Uuid, action: &str) {
    let _ = sqlx::query("INSERT INTO usage_events (user_id, action) VALUES ($1, $2)")
        .bind(user_id)
        .bind(action)
        .execute(&state.db)
        .await;
}
