use std::time::Duration;

use crate::{engine::call_engine, models::Job, state::AppState};

/// Boucle de traitement des jobs en tache de fond.
pub fn spawn(state: AppState) {
    tokio::spawn(async move {
        loop {
            if let Err(e) = tick(&state).await {
                tracing::error!("worker tick error: {e:?}");
            }
            tokio::time::sleep(Duration::from_millis(1000)).await;
        }
    });
}

/// Reclame un job en attente (FOR UPDATE SKIP LOCKED) et le traite.
async fn tick(state: &AppState) -> Result<(), sqlx::Error> {
    let mut tx = state.db.begin().await?;

    let job: Option<Job> = sqlx::query_as::<_, Job>(
        "SELECT id, user_id, project_id, dataset_id, kind, status, payload, result, error, created_at \
         FROM jobs WHERE status = 'queued' ORDER BY created_at \
         FOR UPDATE SKIP LOCKED LIMIT 1",
    )
    .fetch_optional(&mut *tx)
    .await?;

    let Some(job) = job else {
        tx.rollback().await?;
        return Ok(());
    };

    sqlx::query("UPDATE jobs SET status = 'running', started_at = now() WHERE id = $1")
        .bind(job.id)
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;

    process(state, &job).await;
    Ok(())
}

async fn process(state: &AppState, job: &Job) {
    let path = match job.kind.as_str() {
        "profile" => "/v1/profile",
        "ingest" => "/v1/warehouse/ingest",
        "clean_plan" => "/v1/clean/plan",
        "analyze_axes" => "/v1/analyze/axes",
        "doc_dictionary" => "/v1/doc/dictionary",
        "kpi_suggest" => "/v1/kpi/suggest",
        other => {
            fail(state, job, &format!("type de job inconnu: {other}")).await;
            return;
        }
    };

    // Identifiant de suivi : l'engine publie l'avancement sous cette cle et
    // l'interface vient le lire pendant que le job tourne. On reutilise l'id
    // du job — le client le connait deja, rien de plus a transporter.
    let mut payload = job.payload.clone();
    if let Some(champs) = payload.as_object_mut() {
        champs.insert("trace".into(), serde_json::json!(job.id.to_string()));
    }

    match call_engine(state, path, &payload).await {
        Ok(result) => {
            if job.kind == "ingest" {
                finish_ingest(state, job, &result).await;
            }

            // Extraction eventuelle du profil pour enrichir le dataset
            let (profile, rows, cols) = if job.kind == "profile" {
                let profile = result.get("profile").cloned().unwrap_or_else(|| result.clone());
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
                (Some(profile), rows, cols)
            } else {
                (None, None, None)
            };

            let _ = sqlx::query(
                "UPDATE jobs SET status = 'done', result = $1, finished_at = now() WHERE id = $2",
            )
            .bind(result)
            .bind(job.id)
            .execute(&state.db)
            .await;

            if let (Some(profile), Some(ds)) = (profile, job.dataset_id) {
                let _ = sqlx::query(
                    "UPDATE datasets SET profile = $1, row_count = $2, col_count = $3, \
                     status = 'profiled' WHERE id = $4",
                )
                .bind(profile)
                .bind(rows)
                .bind(cols)
                .bind(ds)
                .execute(&state.db)
                .await;
            }
        }
        // Display, pas Debug : c'est ce texte que l'utilisateur lit dans le
        // suivi de tache, `Engine("…")` ne lui dit rien.
        Err(e) => fail(state, job, &e.to_string()).await,
    }
}

/// Fin d'une ingestion : la source passe a l'etat « prete » et le chargement
/// est trace dans l'historique (import initial ou rafraichissement).
async fn finish_ingest(state: &AppState, job: &Job, result: &serde_json::Value) {
    let Some(dataset_id) = job.dataset_id else { return };

    let rows = result.get("rows").and_then(|v| v.as_i64()).map(|v| v as i32);
    let cols = result
        .get("columns")
        .and_then(|v| v.as_array())
        .map(|a| a.len() as i32);
    let profile = result.get("profile").cloned();
    let column_map = result.get("column_map").cloned();

    // Un classeur Excel n'a pas de representation texte a l'upload : c'est
    // l'engine qui renvoie le CSV normalise, et on le conserve ici pour que
    // tout l'aval (rafraichissement, exports) continue de lire du texte.
    let csv = result.get("csv_text").and_then(|v| v.as_str());

    let _ = sqlx::query(
        "UPDATE datasets SET status = 'ready', row_count = $1, col_count = $2, \
                profile = coalesce($3, profile), column_map = coalesce($4, column_map), \
                content = coalesce($5, content), ingested_at = now() \
         WHERE id = $6",
    )
    .bind(rows)
    .bind(cols)
    .bind(profile)
    .bind(column_map)
    .bind(csv)
    .bind(dataset_id)
    .execute(&state.db)
    .await;

    // Tables extraites du tableau plat : chacune devient une source a part
    // entiere, sinon elle existerait dans l'entrepot sans apparaitre nulle
    // part dans l'interface.
    if let Some(liees) = result.get("tables_liees").and_then(|v| v.as_array()) {
        for table in liees {
            let Some(nom) = table.get("table").and_then(|v| v.as_str()) else { continue };
            let lignes = table.get("rows").and_then(|v| v.as_i64()).map(|v| v as i32);
            let colonnes = table
                .get("columns")
                .and_then(|v| v.as_array())
                .map(|a| a.len() as i32);

            let _ = sqlx::query(
                "INSERT INTO datasets \
                    (project_id, user_id, filename, status, table_name, column_map, \
                     row_count, col_count, ingested_at) \
                 VALUES ($1, $2, $3, 'ready', $4, $5, $6, $7, now()) \
                 ON CONFLICT (project_id, table_name) WHERE table_name IS NOT NULL \
                 DO UPDATE SET row_count = EXCLUDED.row_count, \
                               col_count = EXCLUDED.col_count, \
                               column_map = EXCLUDED.column_map, \
                               ingested_at = now()",
            )
            .bind(job.project_id)
            .bind(job.user_id)
            .bind(format!("{nom} (extraite)"))
            .bind(nom)
            .bind(table.get("column_map").cloned())
            .bind(lignes)
            .bind(colonnes)
            .execute(&state.db)
            .await;
        }
    }

    let mode = job
        .payload
        .get("mode")
        .and_then(|v| v.as_str())
        .unwrap_or("replace");
    let _ = sqlx::query(
        "INSERT INTO ingestions (dataset_id, user_id, mode, verdict, row_count, detail) \
         VALUES ($1, $2, $3, 'ok', $4, $5)",
    )
    .bind(dataset_id)
    .bind(job.user_id)
    .bind(mode)
    .bind(rows)
    .bind(result.get("clean_log").cloned().unwrap_or(serde_json::Value::Null))
    .execute(&state.db)
    .await;
}

async fn fail(state: &AppState, job: &Job, msg: &str) {
    let _ = sqlx::query(
        "UPDATE jobs SET status = 'error', error = $1, finished_at = now() WHERE id = $2",
    )
    .bind(msg)
    .bind(job.id)
    .execute(&state.db)
    .await;

    // Une ingestion echouee ne doit pas laisser la source en « pending » :
    // l'UI attendrait indefiniment.
    if job.kind == "ingest" {
        if let Some(dataset_id) = job.dataset_id {
            let _ = sqlx::query("UPDATE datasets SET status = 'error' WHERE id = $1")
                .bind(dataset_id)
                .execute(&state.db)
                .await;
        }
    }
}
