use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;
use serde_json::{json, Value};
use uuid::Uuid;

use crate::{
    auth::AuthUser,
    engine,
    error::ApiError,
    models::{Dataset, Project},
    quota,
    state::AppState,
};

const PROJECT_COLS: &str =
    "id, user_id, workspace_id, name, description, created_at, updated_at";

pub async fn list(
    State(st): State<AppState>,
    user: AuthUser,
) -> Result<Json<Vec<Project>>, ApiError> {
    let rows = sqlx::query_as::<_, Project>(&format!(
        "SELECT {PROJECT_COLS} FROM projects WHERE user_id = $1 ORDER BY updated_at DESC"
    ))
    .bind(user.id)
    .fetch_all(&st.db)
    .await?;
    Ok(Json(rows))
}

#[derive(Deserialize)]
pub struct CreateProject {
    pub name: String,
    pub description: Option<String>,
    /// Espace de destination ; a defaut, l'espace par defaut de l'utilisateur.
    pub workspace_id: Option<Uuid>,
}

pub async fn create(
    State(st): State<AppState>,
    user: AuthUser,
    Json(body): Json<CreateProject>,
) -> Result<(StatusCode, Json<Project>), ApiError> {
    if body.name.trim().is_empty() {
        return Err(ApiError::BadRequest("nom de projet requis".into()));
    }

    let workspace_id = match body.workspace_id {
        Some(id) => sqlx::query_scalar::<_, Uuid>(
            "SELECT id FROM workspaces WHERE id = $1 AND user_id = $2",
        )
        .bind(id)
        .bind(user.id)
        .fetch_optional(&st.db)
        .await?
        .ok_or(ApiError::NotFound)?,
        None => super::workspaces::ensure_default(&st, user.id).await?,
    };

    let p = sqlx::query_as::<_, Project>(&format!(
        "INSERT INTO projects (user_id, workspace_id, name, description) \
         VALUES ($1, $2, $3, $4) RETURNING {PROJECT_COLS}"
    ))
    .bind(user.id)
    .bind(workspace_id)
    .bind(body.name.trim())
    .bind(body.description)
    .fetch_one(&st.db)
    .await?;
    Ok((StatusCode::CREATED, Json(p)))
}

pub async fn get_one(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
) -> Result<Json<Project>, ApiError> {
    let p = sqlx::query_as::<_, Project>(&format!(
        "SELECT {PROJECT_COLS} FROM projects WHERE id = $1 AND user_id = $2"
    ))
    .bind(id)
    .bind(user.id)
    .fetch_optional(&st.db)
    .await?
    .ok_or(ApiError::NotFound)?;
    Ok(Json(p))
}

/// Supprime l'entrepot DuckDB d'un projet. Best effort : la base de
/// metadonnees fait foi, un entrepot orphelin ne doit pas faire echouer
/// la suppression du projet.
pub async fn drop_warehouse(st: &AppState, project_id: Uuid) {
    if let Err(e) = engine::call_engine(
        st,
        "/v1/warehouse/drop",
        &json!({ "project_id": project_id.to_string() }),
    )
    .await
    {
        tracing::warn!("entrepot du projet {} non supprime : {}", project_id, e);
    }
}

/// Supprime un projet et tout ce qui en depend (datasets, jobs : cascade SQL).
pub async fn remove(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, ApiError> {
    let deleted = sqlx::query("DELETE FROM projects WHERE id = $1 AND user_id = $2")
        .bind(id)
        .bind(user.id)
        .execute(&st.db)
        .await?
        .rows_affected();

    if deleted == 0 {
        return Err(ApiError::NotFound);
    }

    drop_warehouse(&st, id).await;
    Ok(StatusCode::NO_CONTENT)
}

/// Liste les datasets d'un projet (avec leur profil) — pour reprendre un projet existant.
pub async fn list_datasets(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
) -> Result<Json<Vec<Dataset>>, ApiError> {
    // Seuls les datasets réellement exploitables (contenu présent) sont retournés
    let rows = sqlx::query_as::<_, Dataset>(
        "SELECT id, project_id, user_id, filename, row_count, col_count, status, profile, created_at \
         FROM datasets WHERE project_id = $1 AND user_id = $2 AND content IS NOT NULL \
         ORDER BY created_at DESC",
    )
    .bind(project_id)
    .bind(user.id)
    .fetch_all(&st.db)
    .await?;
    Ok(Json(rows))
}

#[derive(Deserialize)]
pub struct CreateDataset {
    pub filename: String,
    pub csv_text: String,
}

/// Cree un dataset (contenu CSV inline) et enfile un job de profilage.
/// L'upload de gros fichiers via object storage est la prochaine etape.
pub async fn create_dataset(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
    Json(body): Json<CreateDataset>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    // Verifie la propriete du projet
    let _owned: Uuid =
        sqlx::query_scalar("SELECT id FROM projects WHERE id = $1 AND user_id = $2")
            .bind(project_id)
            .bind(user.id)
            .fetch_optional(&st.db)
            .await?
            .ok_or(ApiError::NotFound)?;

    quota::enforce(&st, user.id, "upload").await?;

    if body.filename.trim().is_empty() || body.csv_text.is_empty() {
        return Err(ApiError::BadRequest("filename et csv_text requis".into()));
    }

    let size = body.csv_text.len() as i64;
    let ds = sqlx::query_as::<_, Dataset>(
        "INSERT INTO datasets (project_id, user_id, filename, size_bytes, status, content) \
         VALUES ($1, $2, $3, $4, 'pending', $5) \
         RETURNING id, project_id, user_id, filename, row_count, col_count, status, profile, created_at",
    )
    .bind(project_id)
    .bind(user.id)
    .bind(body.filename.trim())
    .bind(size)
    .bind(body.csv_text.as_str())
    .fetch_one(&st.db)
    .await?;

    let payload = json!({ "csv_text": body.csv_text, "filename": body.filename });
    let job_id: Uuid = sqlx::query_scalar(
        "INSERT INTO jobs (user_id, project_id, dataset_id, kind, payload) \
         VALUES ($1, $2, $3, 'profile', $4) RETURNING id",
    )
    .bind(user.id)
    .bind(project_id)
    .bind(ds.id)
    .bind(payload)
    .fetch_one(&st.db)
    .await?;

    quota::log(&st, user.id, "upload").await;

    Ok((StatusCode::ACCEPTED, Json(json!({ "dataset": ds, "job_id": job_id }))))
}
