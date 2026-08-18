use axum::{extract::State, Json};
use serde_json::{json, Value};

use crate::{auth::AuthUser, config::tier_limits, error::ApiError, models::User, state::AppState};

pub async fn me(State(st): State<AppState>, user: AuthUser) -> Result<Json<Value>, ApiError> {
    let u = sqlx::query_as::<_, User>("SELECT id, email, tier, created_at FROM users WHERE id = $1")
        .bind(user.id)
        .fetch_one(&st.db)
        .await?;

    let uploads_today: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM usage_events \
         WHERE user_id = $1 AND action = 'upload' AND created_at::date = now()::date",
    )
    .bind(user.id)
    .fetch_one(&st.db)
    .await?;

    let ai_today: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM usage_events \
         WHERE user_id = $1 AND action = 'ai_query' AND created_at::date = now()::date",
    )
    .bind(user.id)
    .fetch_one(&st.db)
    .await?;

    let (max_up, max_ai) = tier_limits(&u.tier);

    Ok(Json(json!({
        "user": u,
        "usage": { "uploads_today": uploads_today, "ai_queries_today": ai_today },
        "limits": { "uploads_per_day": max_up, "ai_queries_per_day": max_ai }
    })))
}
