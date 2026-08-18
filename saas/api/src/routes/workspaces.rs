//! Espaces de travail : premier niveau d'organisation (un espace contient des projets).

use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;
use uuid::Uuid;

use crate::{auth::AuthUser, error::ApiError, models::Workspace, state::AppState};

/// Renvoie l'espace par defaut de l'utilisateur, en le creant au besoin.
/// Utilise a la creation d'un projet quand aucun espace n'est precise.
pub async fn ensure_default(st: &AppState, user_id: Uuid) -> Result<Uuid, ApiError> {
    if let Some(id) = sqlx::query_scalar::<_, Uuid>(
        "SELECT id FROM workspaces WHERE user_id = $1 ORDER BY created_at LIMIT 1",
    )
    .bind(user_id)
    .fetch_optional(&st.db)
    .await?
    {
        return Ok(id);
    }
    let id = sqlx::query_scalar::<_, Uuid>(
        "INSERT INTO workspaces (user_id, name) VALUES ($1, 'Espace principal') RETURNING id",
    )
    .bind(user_id)
    .fetch_one(&st.db)
    .await?;
    Ok(id)
}

pub async fn list(
    State(st): State<AppState>,
    user: AuthUser,
) -> Result<Json<Vec<Workspace>>, ApiError> {
    // Un utilisateur a toujours au moins un espace : l'UI n'a pas de cas vide a gerer.
    ensure_default(&st, user.id).await?;
    let rows = sqlx::query_as::<_, Workspace>(
        "SELECT id, user_id, name, created_at, updated_at \
         FROM workspaces WHERE user_id = $1 ORDER BY created_at",
    )
    .bind(user.id)
    .fetch_all(&st.db)
    .await?;
    Ok(Json(rows))
}

#[derive(Deserialize)]
pub struct WorkspaceBody {
    pub name: String,
}

pub async fn create(
    State(st): State<AppState>,
    user: AuthUser,
    Json(body): Json<WorkspaceBody>,
) -> Result<(StatusCode, Json<Workspace>), ApiError> {
    if body.name.trim().is_empty() {
        return Err(ApiError::BadRequest("nom d'espace requis".into()));
    }
    let w = sqlx::query_as::<_, Workspace>(
        "INSERT INTO workspaces (user_id, name) VALUES ($1, $2) \
         RETURNING id, user_id, name, created_at, updated_at",
    )
    .bind(user.id)
    .bind(body.name.trim())
    .fetch_one(&st.db)
    .await?;
    Ok((StatusCode::CREATED, Json(w)))
}

pub async fn rename(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
    Json(body): Json<WorkspaceBody>,
) -> Result<Json<Workspace>, ApiError> {
    if body.name.trim().is_empty() {
        return Err(ApiError::BadRequest("nom d'espace requis".into()));
    }
    let w = sqlx::query_as::<_, Workspace>(
        "UPDATE workspaces SET name = $1, updated_at = now() WHERE id = $2 AND user_id = $3 \
         RETURNING id, user_id, name, created_at, updated_at",
    )
    .bind(body.name.trim())
    .bind(id)
    .bind(user.id)
    .fetch_optional(&st.db)
    .await?
    .ok_or(ApiError::NotFound)?;
    Ok(Json(w))
}

/// Supprime un espace et, en cascade, ses projets et leurs donnees.
/// Le dernier espace n'est pas supprimable : l'utilisateur doit toujours
/// avoir un endroit ou creer un projet.
pub async fn remove(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, ApiError> {
    let count: i64 = sqlx::query_scalar("SELECT count(*) FROM workspaces WHERE user_id = $1")
        .bind(user.id)
        .fetch_one(&st.db)
        .await?;
    if count <= 1 {
        return Err(ApiError::BadRequest(
            "impossible de supprimer le dernier espace de travail".into(),
        ));
    }

    // Les entrepots des projets de l'espace sont supprimes avant la cascade SQL,
    // qui effacerait les identifiants dont on a besoin pour les retrouver.
    let project_ids: Vec<Uuid> =
        sqlx::query_scalar("SELECT id FROM projects WHERE workspace_id = $1 AND user_id = $2")
            .bind(id)
            .bind(user.id)
            .fetch_all(&st.db)
            .await?;

    let deleted = sqlx::query("DELETE FROM workspaces WHERE id = $1 AND user_id = $2")
        .bind(id)
        .bind(user.id)
        .execute(&st.db)
        .await?
        .rows_affected();
    if deleted == 0 {
        return Err(ApiError::NotFound);
    }

    for pid in project_ids {
        crate::routes::projects::drop_warehouse(&st, pid).await;
    }
    Ok(StatusCode::NO_CONTENT)
}
