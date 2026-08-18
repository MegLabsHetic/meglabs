use axum::{
    extract::{Path, State},
    Json,
};
use serde_json::Value;
use uuid::Uuid;

use crate::{auth::AuthUser, engine, error::ApiError, models::Job, state::AppState};

/// Etat d'un job. Tant qu'il tourne, on y joint l'avancement detaille publie
/// par l'engine : « lecture du fichier », « chargement dans l'entrepot »…
/// Sans lui, l'interface ne pourrait afficher que « en cours » pendant toute
/// la duree du traitement.
pub async fn get_one(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    let job = sqlx::query_as::<_, Job>(
        "SELECT id, user_id, project_id, dataset_id, kind, status, payload, result, error, created_at \
         FROM jobs WHERE id = $1 AND user_id = $2",
    )
    .bind(id)
    .bind(user.id)
    .fetch_optional(&st.db)
    .await?
    .ok_or(ApiError::NotFound)?;

    let statut = job.status.clone();
    let mut sortie =
        serde_json::to_value(job).map_err(|e| ApiError::Internal(format!("serialisation: {e}")))?;

    // Le payload contient le fichier envoye. Le renvoyer a chaque sondage —
    // une fois par seconde pendant toute l'ingestion — ferait transiter le
    // classeur des dizaines de fois pour une information que personne ne lit.
    if let Some(champs) = sortie.as_object_mut() {
        champs.remove("payload");
    }

    // Le suivi ne vit que pendant le traitement : inutile de l'interroger
    // pour un job en attente ou deja termine.
    if statut == "running" {
        if let Some(p) = engine::get_engine(&st, &format!("/v1/progress/{id}")).await {
            if p.get("connu").and_then(Value::as_bool).unwrap_or(false) {
                sortie["progress"] = p;
            }
        }
    }

    Ok(Json(sortie))
}
