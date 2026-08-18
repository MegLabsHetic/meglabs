use axum::{
    extract::{Path, State},
    Json,
};
use serde::Deserialize;
use serde_json::{json, Value};
use uuid::Uuid;

use crate::{auth::AuthUser, engine, error::ApiError, quota, state::AppState};

/// Charge le contenu CSV d'un dataset appartenant a l'utilisateur.
async fn load_content(st: &AppState, dataset_id: Uuid, user_id: Uuid) -> Result<String, ApiError> {
    let row: Option<Option<String>> =
        sqlx::query_scalar::<_, Option<String>>(
            "SELECT content FROM datasets WHERE id = $1 AND user_id = $2",
        )
        .bind(dataset_id)
        .bind(user_id)
        .fetch_optional(&st.db)
        .await?;
    row.ok_or(ApiError::NotFound)?
        .ok_or(ApiError::BadRequest("dataset sans contenu".into()))
}

/// Charge le profil (JSON) d'un dataset appartenant a l'utilisateur.
async fn load_profile(st: &AppState, dataset_id: Uuid, user_id: Uuid) -> Result<Value, ApiError> {
    let row: Option<Option<Value>> =
        sqlx::query_scalar::<_, Option<Value>>(
            "SELECT profile FROM datasets WHERE id = $1 AND user_id = $2",
        )
        .bind(dataset_id)
        .bind(user_id)
        .fetch_optional(&st.db)
        .await?;
    row.ok_or(ApiError::NotFound)?
        .ok_or(ApiError::BadRequest("dataset pas encore profile".into()))
}

/// Charge contenu + profil en un appel.
async fn load_content_profile(
    st: &AppState,
    dataset_id: Uuid,
    user_id: Uuid,
) -> Result<(String, Value), ApiError> {
    let row: Option<(Option<String>, Option<Value>)> = sqlx::query_as(
        "SELECT content, profile FROM datasets WHERE id = $1 AND user_id = $2",
    )
    .bind(dataset_id)
    .bind(user_id)
    .fetch_optional(&st.db)
    .await?;
    let (content, profile) = row.ok_or(ApiError::NotFound)?;
    Ok((
        content.ok_or(ApiError::BadRequest("dataset sans contenu".into()))?,
        profile.unwrap_or(Value::Null),
    ))
}

/// Renvoie la cle IA plateforme, ou une erreur si absente.
fn ai_key(st: &AppState) -> Result<&str, ApiError> {
    if st.cfg.anthropic_api_key.is_empty() {
        Err(ApiError::BadRequest(
            "Cle Anthropic non configuree sur la plateforme (ANTHROPIC_API_KEY)".into(),
        ))
    } else {
        Ok(&st.cfg.anthropic_api_key)
    }
}

/// Etape 2 — plan de nettoyage propose par l'IA (operation IA, comptee au quota).
pub async fn clean_plan(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    let content = load_content(&st, id, user.id).await?;
    quota::enforce(&st, user.id, "ai_query").await?;

    if st.cfg.anthropic_api_key.is_empty() {
        return Err(ApiError::BadRequest(
            "Cle Anthropic non configuree sur la plateforme (ANTHROPIC_API_KEY)".into(),
        ));
    }

    let body = json!({ "csv_text": content, "api_key": st.cfg.anthropic_api_key });
    let res = engine::call_engine(&st, "/v1/clean/plan", &body).await?;
    quota::log(&st, user.id, "ai_query").await;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct ApplyBody {
    pub actions: Vec<Value>,
    #[serde(default)]
    pub persist: bool,
}

/// Etape 2 — application deterministe des actions validees par l'utilisateur.
pub async fn clean_apply(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
    Json(body): Json<ApplyBody>,
) -> Result<Json<Value>, ApiError> {
    let content = load_content(&st, id, user.id).await?;
    let call = json!({ "csv_text": content, "actions": body.actions });
    let res = engine::call_engine(&st, "/v1/clean/apply", &call).await?;

    if body.persist {
        if let Some(cleaned_csv) = res.get("cleaned_csv").and_then(|v| v.as_str()) {
            sqlx::query("UPDATE datasets SET content = $1 WHERE id = $2")
                .bind(cleaned_csv)
                .bind(id)
                .execute(&st.db)
                .await?;

            // Re-profilage du dataset nettoye
            let prof_body = json!({ "csv_text": cleaned_csv });
            if let Ok(profres) = engine::call_engine(&st, "/v1/profile", &prof_body).await {
                let profile = profres.get("profile").cloned().unwrap_or(Value::Null);
                let rows = profile
                    .get("shape")
                    .and_then(|s| s.get("rows"))
                    .and_then(|v| v.as_i64())
                    .map(|v| v as i32);
                let cols = profile
                    .get("shape")
                    .and_then(|s| s.get("columns"))
                    .and_then(|v| v.as_i64())
                    .map(|v| v as i32);
                let _ = sqlx::query(
                    "UPDATE datasets SET profile = $1, row_count = $2, col_count = $3, \
                     status = 'cleaned' WHERE id = $4",
                )
                .bind(profile)
                .bind(rows)
                .bind(cols)
                .bind(id)
                .execute(&st.db)
                .await;
            }
        }
    }

    // On ne renvoie pas le CSV complet au client
    let mut out = res;
    if let Some(obj) = out.as_object_mut() {
        obj.remove("cleaned_csv");
    }
    Ok(Json(out))
}

// ════════════════════════════════════════════════
// Etape 3 — Exploration (EDA)
// ════════════════════════════════════════════════

/// Axes d'analyse proposes par l'IA (operation IA).
pub async fn analyze_axes(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    let profile = load_profile(&st, id, user.id).await?;
    quota::enforce(&st, user.id, "ai_query").await?;
    let key = ai_key(&st)?;
    let res = engine::call_engine(
        &st,
        "/v1/analyze/axes",
        &json!({ "profile": profile, "api_key": key }),
    )
    .await?;
    quota::log(&st, user.id, "ai_query").await;
    Ok(Json(res))
}

pub async fn analyze_correlations(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    let content = load_content(&st, id, user.id).await?;
    let res = engine::call_engine(
        &st,
        "/v1/analyze/correlations",
        &json!({ "csv_text": content }),
    )
    .await?;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct SegmentBody {
    pub columns: Vec<String>,
    pub n_clusters: Option<i64>,
}

pub async fn analyze_segment(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
    Json(b): Json<SegmentBody>,
) -> Result<Json<Value>, ApiError> {
    let content = load_content(&st, id, user.id).await?;
    let res = engine::call_engine(
        &st,
        "/v1/analyze/segment",
        &json!({ "csv_text": content, "columns": b.columns, "n_clusters": b.n_clusters.unwrap_or(3) }),
    )
    .await?;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct TimeBody {
    pub date_col: String,
}

pub async fn analyze_time(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
    Json(b): Json<TimeBody>,
) -> Result<Json<Value>, ApiError> {
    let content = load_content(&st, id, user.id).await?;
    let res = engine::call_engine(
        &st,
        "/v1/analyze/time",
        &json!({ "csv_text": content, "date_col": b.date_col }),
    )
    .await?;
    Ok(Json(res))
}

// ════════════════════════════════════════════════
// Etape 4 — Documentation
// ════════════════════════════════════════════════

pub async fn doc_dictionary(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    let content = load_content(&st, id, user.id).await?;
    quota::enforce(&st, user.id, "ai_query").await?;
    let key = ai_key(&st)?;
    let res = engine::call_engine(
        &st,
        "/v1/doc/dictionary",
        &json!({ "csv_text": content, "api_key": key }),
    )
    .await?;
    quota::log(&st, user.id, "ai_query").await;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct WarehouseBody {
    pub dictionary: Option<Value>,
}

pub async fn doc_warehouse(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
    Json(b): Json<WarehouseBody>,
) -> Result<Json<Value>, ApiError> {
    let content = load_content(&st, id, user.id).await?;
    quota::enforce(&st, user.id, "ai_query").await?;
    let key = ai_key(&st)?;
    let res = engine::call_engine(
        &st,
        "/v1/doc/warehouse",
        &json!({ "csv_text": content, "dictionary": b.dictionary, "api_key": key }),
    )
    .await?;
    quota::log(&st, user.id, "ai_query").await;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct ExportBody {
    pub dictionary: Value,
    pub model: Option<Value>,
    pub dataset_name: Option<String>,
}

pub async fn doc_export(
    State(st): State<AppState>,
    _user: AuthUser,
    Path(_id): Path<Uuid>,
    Json(b): Json<ExportBody>,
) -> Result<Json<Value>, ApiError> {
    let res = engine::call_engine(
        &st,
        "/v1/doc/export",
        &json!({
            "dictionary": b.dictionary,
            "model": b.model,
            "dataset_name": b.dataset_name.unwrap_or_else(|| "dataset".into()),
        }),
    )
    .await?;
    Ok(Json(res))
}

// ════════════════════════════════════════════════
// Etape 5 — KPIs
// ════════════════════════════════════════════════

#[derive(Deserialize)]
pub struct KpiSuggestBody {
    pub dictionary: Option<Value>,
}

pub async fn kpi_suggest(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
    Json(b): Json<KpiSuggestBody>,
) -> Result<Json<Value>, ApiError> {
    let profile = load_profile(&st, id, user.id).await?;
    quota::enforce(&st, user.id, "ai_query").await?;
    let key = ai_key(&st)?;
    let res = engine::call_engine(
        &st,
        "/v1/kpi/suggest",
        &json!({ "profile": profile, "dictionary": b.dictionary, "api_key": key }),
    )
    .await?;
    quota::log(&st, user.id, "ai_query").await;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct KpiComputeBody {
    pub spec: Value,
    #[serde(default)]
    pub filters: Option<Value>,
}

pub async fn kpi_compute(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
    Json(b): Json<KpiComputeBody>,
) -> Result<Json<Value>, ApiError> {
    let content = load_content(&st, id, user.id).await?;
    let res = engine::call_engine(
        &st,
        "/v1/kpi/compute",
        &json!({ "csv_text": content, "spec": b.spec, "filters": b.filters }),
    )
    .await?;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct ChatBody {
    pub message: String,
    #[serde(default)]
    pub history: Vec<Value>,
}

/// Assistant conversationnel : répond + propose une visualisation calculée.
pub async fn chat(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
    Json(b): Json<ChatBody>,
) -> Result<Json<Value>, ApiError> {
    let (content, profile) = load_content_profile(&st, id, user.id).await?;
    quota::enforce(&st, user.id, "ai_query").await?;
    let key = ai_key(&st)?;
    let res = engine::call_engine(
        &st,
        "/v1/chat",
        &json!({
            "csv_text": content,
            "profile": profile,
            "message": b.message,
            "history": b.history,
            "api_key": key,
        }),
    )
    .await?;
    quota::log(&st, user.id, "ai_query").await;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct ValuesBody {
    pub column: String,
}

/// Valeurs distinctes d'une colonne (pour les controles de filtre du dashboard).
pub async fn column_values(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
    Json(b): Json<ValuesBody>,
) -> Result<Json<Value>, ApiError> {
    let content = load_content(&st, id, user.id).await?;
    let res = engine::call_engine(
        &st,
        "/v1/analyze/values",
        &json!({ "csv_text": content, "column": b.column }),
    )
    .await?;
    Ok(Json(res))
}
