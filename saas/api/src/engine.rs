use serde_json::Value;

use crate::{error::ApiError, state::AppState};

/// Appelle le service Python (engine) et renvoie sa reponse JSON.
pub async fn call_engine(state: &AppState, path: &str, body: &Value) -> Result<Value, ApiError> {
    let url = format!("{}{}", state.cfg.engine_url, path);
    let resp = state.http.post(&url).json(body).send().await?;
    if !resp.status().is_success() {
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        tracing::error!("engine {status} sur {path}: {text}");
        // L'engine explique deja ses refus en clair dans `detail` (« colonne
        // introuvable », « fichier illisible »…). C'est cette phrase que
        // l'utilisateur doit lire, pas un code HTTP suivi d'un blob JSON.
        let motif = serde_json::from_str::<Value>(&text)
            .ok()
            .and_then(|v| v.get("detail").and_then(|d| d.as_str()).map(str::to_string))
            .unwrap_or_else(|| "le moteur d'analyse a refuse le traitement".into());
        return Err(ApiError::Engine(motif));
    }
    Ok(resp.json::<Value>().await?)
}

/// Lecture simple cote engine (suivi d'avancement). Une erreur n'est pas
/// fatale ici : l'appelant s'en passe et affiche simplement moins de detail.
pub async fn get_engine(state: &AppState, path: &str) -> Option<Value> {
    let url = format!("{}{}", state.cfg.engine_url, path);
    let resp = state.http.get(&url).send().await.ok()?;
    if !resp.status().is_success() {
        return None;
    }
    resp.json::<Value>().await.ok()
}
