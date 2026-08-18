//! Entrepot analytique : ingestion ETL, requetes SQL, chat et tableau de bord.
//!
//! Le contenu du CSV ne circule plus a chaque calcul : il est charge une fois
//! dans l'entrepot DuckDB du projet, puis tout se calcule en SQL. Postgres
//! garde la metadonnee (nom de table, correspondance des colonnes, widgets).

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
    models::{Dashboard, DatasetSource, Widget},
    quota,
    state::AppState,
};

/// Verifie que le projet appartient bien a l'utilisateur.
async fn owned_project(st: &AppState, project_id: Uuid, user_id: Uuid) -> Result<(), ApiError> {
    sqlx::query_scalar::<_, Uuid>("SELECT id FROM projects WHERE id = $1 AND user_id = $2")
        .bind(project_id)
        .bind(user_id)
        .fetch_optional(&st.db)
        .await?
        .ok_or(ApiError::NotFound)?;
    Ok(())
}

fn ai_key(st: &AppState) -> Result<&str, ApiError> {
    if st.cfg.anthropic_api_key.is_empty() {
        Err(ApiError::BadRequest(
            "Cle Anthropic non configuree sur la plateforme (ANTHROPIC_API_KEY)".into(),
        ))
    } else {
        Ok(&st.cfg.anthropic_api_key)
    }
}

/// Translitteration d'un caractere non latin. Sans elle, « المبيعات.csv »
/// ne laisse aucun caractere ASCII et la table s'appellerait « t_ » — un nom
/// que ni l'utilisateur ni l'agent SQL ne peut relier a quoi que ce soit.
/// Doit rester aligne sur `transliterate` cote engine.
fn translit(ch: char) -> &'static str {
    match ch {
        'à' | 'â' | 'ä' | 'á' => "a",
        'é' | 'è' | 'ê' | 'ë' => "e",
        'î' | 'ï' | 'í' => "i",
        'ô' | 'ö' | 'ó' => "o",
        'ù' | 'û' | 'ü' | 'ú' => "u",
        'ç' => "c",
        'ا' | 'أ' | 'آ' | 'ى' | 'ة' | 'ع' => "a",
        'إ' => "i",
        'ب' => "b",
        'ت' => "t",
        'ث' => "th",
        'ج' => "j",
        'ح' | 'ه' => "h",
        'خ' => "kh",
        'د' => "d",
        'ذ' => "dh",
        'ر' => "r",
        'ز' => "z",
        'س' => "s",
        'ش' => "sh",
        'ص' => "s",
        'ض' => "d",
        'ط' => "t",
        'ظ' => "z",
        'غ' => "gh",
        'ف' => "f",
        'ق' => "q",
        'ك' => "k",
        'ل' => "l",
        'م' => "m",
        'ن' => "n",
        'و' | 'ؤ' => "w",
        'ي' | 'ئ' => "y",
        '٠' => "0",
        '١' => "1",
        '٢' => "2",
        '٣' => "3",
        '٤' => "4",
        '٥' => "5",
        '٦' => "6",
        '٧' => "7",
        '٨' => "8",
        '٩' => "9",
        _ => "",
    }
}

/// « Ventes 2024.csv » -> « ventes_2024 », « المبيعات.csv » -> « almbyaat ».
/// Doit rester aligne sur `sql_identifier` cote engine : c'est le meme nom
/// de table des deux cotes.
fn table_slug(filename: &str) -> String {
    let stem = filename.rsplit_once('.').map(|(s, _)| s).unwrap_or(filename);
    let mut out = String::new();
    let mut last_underscore = false;
    for ch in stem.chars() {
        let lower = ch.to_ascii_lowercase();
        let mapped: String = if lower.is_ascii_alphanumeric() {
            lower.to_string()
        } else {
            translit(ch).to_string()
        };
        if !mapped.is_empty() {
            out.push_str(&mapped);
            last_underscore = false;
        } else if !last_underscore && !out.is_empty() {
            out.push('_');
            last_underscore = true;
        }
    }
    let out = out.trim_end_matches('_').to_string();
    if out.is_empty() || out.starts_with(|c: char| c.is_ascii_digit()) {
        format!("t_{out}")
    } else {
        out.chars().take(60).collect()
    }
}

/// Noms de table deja occupes dans le projet.
async fn tables_prises(st: &AppState, project_id: Uuid) -> Result<Vec<String>, ApiError> {
    Ok(sqlx::query_scalar(
        "SELECT table_name FROM datasets WHERE project_id = $1 AND table_name IS NOT NULL",
    )
    .bind(project_id)
    .fetch_all(&st.db)
    .await?)
}

/// Premier nom libre a partir d'une base (suffixe numerique en cas de collision).
fn nom_libre(base: &str, pris: &[String]) -> Result<String, ApiError> {
    if !pris.iter().any(|t| t == base) {
        return Ok(base.to_string());
    }
    for n in 2..1000 {
        let candidat = format!("{base}_{n}");
        if !pris.iter().any(|t| t == &candidat) {
            return Ok(candidat);
        }
    }
    Err(ApiError::BadRequest("trop de sources homonymes".into()))
}

// ════════════════════════════════════════════════
// Sources : import initial et rafraichissement
// ════════════════════════════════════════════════

#[derive(Deserialize)]
pub struct IngestBody {
    pub filename: String,
    /// Fichier texte (CSV). Absent pour un classeur Excel.
    #[serde(default)]
    pub csv_text: Option<String>,
    /// Classeur Excel encode en base64 : un .xlsx ne survit pas au transport
    /// en texte, il faut le vehiculer en binaire.
    #[serde(default)]
    pub file_base64: Option<String>,
    /// Feuille voulue dans un classeur ; a defaut, la premiere non vide.
    #[serde(default)]
    pub sheet: Option<String>,
    /// Actions de nettoyage validees par l'utilisateur, appliquees avant chargement.
    #[serde(default)]
    pub clean_actions: Vec<Value>,
    /// Tables a extraire du tableau plat, validees par l'utilisateur.
    #[serde(default)]
    pub decoupage: Vec<Value>,
}

/// Reconnait le format d'un fichier et liste les feuilles d'un classeur.
/// Appele avant l'ingestion pour laisser l'utilisateur choisir sa feuille.
pub async fn inspect_file(
    State(st): State<AppState>,
    _user: AuthUser,
    Json(body): Json<Value>,
) -> Result<Json<Value>, ApiError> {
    let res = engine::call_engine(&st, "/v1/files/inspect", &body).await?;
    Ok(Json(res))
}

/// Diagnostic de qualite d'un fichier avant chargement : doublons, colonnes
/// vides, nombres stockes en texte. Entierement deterministe cote engine,
/// donc ni cout ni quota.
pub async fn diagnose_file(
    State(st): State<AppState>,
    _user: AuthUser,
    Json(body): Json<Value>,
) -> Result<Json<Value>, ApiError> {
    let res = engine::call_engine(&st, "/v1/files/diagnose", &body).await?;
    Ok(Json(res))
}

/// Liste les sources d'un projet (les tables de son entrepot).
pub async fn list_sources(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
) -> Result<Json<Vec<DatasetSource>>, ApiError> {
    owned_project(&st, project_id, user.id).await?;
    let rows = sqlx::query_as::<_, DatasetSource>(
        "SELECT id, project_id, filename, table_name, column_map, row_count, col_count, \
                status, profile, ingested_at, created_at \
         FROM datasets WHERE project_id = $1 AND table_name IS NOT NULL \
         ORDER BY created_at",
    )
    .bind(project_id)
    .fetch_all(&st.db)
    .await?;
    Ok(Json(rows))
}

/// Import initial : cree la source puis lance la pipeline d'ingestion.
pub async fn ingest(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
    Json(body): Json<IngestBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    owned_project(&st, project_id, user.id).await?;
    quota::enforce(&st, user.id, "upload").await?;

    if body.filename.trim().is_empty() {
        return Err(ApiError::BadRequest("nom de fichier requis".into()));
    }
    let csv = body.csv_text.as_deref().unwrap_or_default();
    let binaire = body.file_base64.as_deref().unwrap_or_default();
    if csv.is_empty() && binaire.is_empty() {
        return Err(ApiError::BadRequest("fichier vide".into()));
    }

    let mut pris = tables_prises(&st, project_id).await?;
    let table = nom_libre(&table_slug(&body.filename), &pris)?;
    pris.push(table.clone());

    // Les tables extraites prennent elles aussi un nom libre. Sans cela, deux
    // sources produisant chacune une dimension « clients » se marcheraient
    // dessus : la seconde ecraserait la premiere en silence.
    let mut decoupage = body.decoupage.clone();
    for d in decoupage.iter_mut() {
        let suggere = d
            .get("nom")
            .or_else(|| d.get("nom_suggere"))
            .and_then(Value::as_str)
            .unwrap_or("dimension");
        let nom = nom_libre(&table_slug(suggere), &pris)?;
        pris.push(nom.clone());
        if let Some(champs) = d.as_object_mut() {
            champs.insert("nom".into(), Value::String(nom));
        }
    }

    let size = (csv.len() + binaire.len()) as i64;

    let dataset_id: Uuid = sqlx::query_scalar(
        "INSERT INTO datasets (project_id, user_id, filename, size_bytes, status, content, \
                table_name, clean_actions, decoupage) \
         VALUES ($1, $2, $3, $4, 'pending', $5, $6, $7, $8) RETURNING id",
    )
    .bind(project_id)
    .bind(user.id)
    .bind(body.filename.trim())
    .bind(size)
    // Un classeur n'a pas de representation texte a ce stade : le CSV
    // normalise sera ecrit par le worker apres l'ingestion.
    .bind(body.csv_text.as_deref())
    .bind(&table)
    // La pipeline retenue decrit la source : elle sera rejouee a chaque mise
    // a jour, sinon le fichier suivant repartirait brut.
    .bind(Value::Array(body.clean_actions.clone()))
    .bind(Value::Array(decoupage.clone()))
    .fetch_one(&st.db)
    .await?;

    let payload = json!({
        "project_id": project_id.to_string(),
        "table": table,
        "csv_text": body.csv_text,
        "file_base64": body.file_base64,
        "sheet": body.sheet,
        "filename": body.filename,
        "mode": "replace",
        "clean_actions": body.clean_actions,
        "decoupage": decoupage,
        "return_csv": true,
    });
    let job_id: Uuid = sqlx::query_scalar(
        "INSERT INTO jobs (user_id, project_id, dataset_id, kind, payload) \
         VALUES ($1, $2, $3, 'ingest', $4) RETURNING id",
    )
    .bind(user.id)
    .bind(project_id)
    .bind(dataset_id)
    .bind(payload)
    .fetch_one(&st.db)
    .await?;

    quota::log(&st, user.id, "upload").await;
    Ok((
        StatusCode::ACCEPTED,
        Json(json!({ "dataset_id": dataset_id, "table": table, "job_id": job_id })),
    ))
}

/// Une source et la pipeline retenue lors de son import.
struct Source {
    project_id: Uuid,
    table: String,
    /// Corrections validees a l'import, rejouees a chaque mise a jour.
    clean_actions: Value,
    /// Decoupage en tables liees, rejoue de meme.
    decoupage: Value,
}

/// Charge une source appartenant a l'utilisateur.
async fn load_source(st: &AppState, dataset_id: Uuid, user_id: Uuid) -> Result<Source, ApiError> {
    let row: Option<(Uuid, Option<String>, Option<Value>, Option<Value>)> = sqlx::query_as(
        "SELECT project_id, table_name, clean_actions, decoupage \
         FROM datasets WHERE id = $1 AND user_id = $2",
    )
    .bind(dataset_id)
    .bind(user_id)
    .fetch_optional(&st.db)
    .await?;
    let (project_id, table, clean_actions, decoupage) = row.ok_or(ApiError::NotFound)?;
    Ok(Source {
        project_id,
        table: table.ok_or(ApiError::BadRequest("source non ingeree".into()))?,
        clean_actions: clean_actions.unwrap_or_else(|| json!([])),
        decoupage: decoupage.unwrap_or_else(|| json!([])),
    })
}

#[derive(Deserialize)]
pub struct RefreshCheckBody {
    #[serde(default)]
    pub csv_text: Option<String>,
    #[serde(default)]
    pub file_base64: Option<String>,
    #[serde(default)]
    pub sheet: Option<String>,
    /// Langue de l'interface : sert aux agents qui n'ont pas de question
    /// utilisateur d'ou deduire la langue de leur reponse.
    #[serde(default = "default_langue")]
    pub langue: String,
}

fn default_langue() -> String {
    "fr".into()
}

/// Etape 1 du rafraichissement : la structure du fichier est-elle la bonne ?
/// Aucune donnee n'est modifiee ici — on renvoie un verdict a valider.
///
/// La comparaison porte sur ce qui sera REELLEMENT charge : la pipeline de
/// l'import est d'abord rejouee sur le nouveau fichier. Sans cela, un tableau
/// decoupe en tables liees ferait apparaitre ses colonnes de dimension comme
/// « en trop », et un montant en texte comme un changement de type.
pub async fn refresh_check(
    State(st): State<AppState>,
    user: AuthUser,
    Path(dataset_id): Path<Uuid>,
    Json(body): Json<RefreshCheckBody>,
) -> Result<Json<Value>, ApiError> {
    let src = load_source(&st, dataset_id, user.id).await?;
    let key = ai_key(&st)?;
    let res = engine::call_engine(
        &st,
        "/v1/warehouse/schema/check",
        &json!({
            "project_id": src.project_id.to_string(),
            "table": src.table,
            "csv_text": body.csv_text,
            "file_base64": body.file_base64,
            "sheet": body.sheet,
            "langue": body.langue,
            "clean_actions": src.clean_actions,
            "decoupage": src.decoupage,
            "api_key": key,
        }),
    )
    .await?;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct RefreshApplyBody {
    #[serde(default)]
    pub csv_text: Option<String>,
    #[serde(default)]
    pub file_base64: Option<String>,
    #[serde(default)]
    pub sheet: Option<String>,
    /// "replace" (remplace les donnees) ou "append" (ajoute les nouvelles lignes).
    #[serde(default = "default_mode")]
    pub mode: String,
    /// Corrections de colonnes validees par l'utilisateur.
    #[serde(default)]
    pub renames: Value,
    #[serde(default)]
    pub clean_actions: Vec<Value>,
}

fn default_mode() -> String {
    "replace".into()
}

/// Etape 2 du rafraichissement : relance la pipeline d'ingestion.
/// Les widgets du tableau de bord ne changent pas — leur SQL est rejoue
/// sur les nouvelles donnees au prochain affichage.
pub async fn refresh_apply(
    State(st): State<AppState>,
    user: AuthUser,
    Path(dataset_id): Path<Uuid>,
    Json(body): Json<RefreshApplyBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    let src = load_source(&st, dataset_id, user.id).await?;
    quota::enforce(&st, user.id, "upload").await?;

    if body.mode != "replace" && body.mode != "append" {
        return Err(ApiError::BadRequest("mode invalide".into()));
    }

    sqlx::query("UPDATE datasets SET content = $1, status = 'pending' WHERE id = $2")
        .bind(body.csv_text.as_deref())
        .bind(dataset_id)
        .execute(&st.db)
        .await?;

    // La pipeline de l'import est rejouee telle quelle : meme nettoyage, meme
    // decoupage. C'est ce qui garantit qu'une colonne typee le reste et que
    // les tables liees ne se recollent pas. L'appelant peut ajouter des
    // corrections propres a ce fichier-ci, jamais en retirer.
    let mut actions = match src.clean_actions {
        Value::Array(a) => a,
        _ => vec![],
    };
    actions.extend(body.clean_actions);

    let payload = json!({
        "project_id": src.project_id.to_string(),
        "table": src.table,
        "csv_text": body.csv_text,
        "file_base64": body.file_base64,
        "sheet": body.sheet,
        "mode": body.mode,
        "renames": body.renames,
        "clean_actions": actions,
        "decoupage": src.decoupage,
        "return_csv": true,
    });
    let job_id: Uuid = sqlx::query_scalar(
        "INSERT INTO jobs (user_id, project_id, dataset_id, kind, payload) \
         VALUES ($1, $2, $3, 'ingest', $4) RETURNING id",
    )
    .bind(user.id)
    .bind(src.project_id)
    .bind(dataset_id)
    .bind(payload)
    .fetch_one(&st.db)
    .await?;

    quota::log(&st, user.id, "upload").await;
    Ok((StatusCode::ACCEPTED, Json(json!({ "job_id": job_id }))))
}

// ════════════════════════════════════════════════
// Lecture de l'entrepot
// ════════════════════════════════════════════════

pub async fn schema(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    owned_project(&st, project_id, user.id).await?;
    let res = engine::call_engine(
        &st,
        "/v1/warehouse/schema",
        &json!({ "project_id": project_id.to_string() }),
    )
    .await?;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct SqlBody {
    pub sql: String,
    #[serde(default)]
    pub limit: Option<i64>,
}

/// Requete SQL libre sur l'entrepot (lecture seule, garde-fous cote engine).
pub async fn run_sql(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
    Json(b): Json<SqlBody>,
) -> Result<Json<Value>, ApiError> {
    owned_project(&st, project_id, user.id).await?;
    let res = engine::call_engine(
        &st,
        "/v1/warehouse/sql",
        &json!({
            "project_id": project_id.to_string(),
            "sql": b.sql,
            "limit": b.limit.unwrap_or(5000),
        }),
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

/// Assistant conversationnel adosse a l'entrepot : question -> SQL -> resultat.
pub async fn chat(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
    Json(b): Json<ChatBody>,
) -> Result<Json<Value>, ApiError> {
    owned_project(&st, project_id, user.id).await?;
    quota::enforce(&st, user.id, "ai_query").await?;
    let key = ai_key(&st)?;
    let res = engine::call_engine(
        &st,
        "/v1/warehouse/chat",
        &json!({
            "project_id": project_id.to_string(),
            "message": b.message,
            "history": b.history,
            "api_key": key,
        }),
    )
    .await?;
    quota::log(&st, user.id, "ai_query").await;
    Ok(Json(res))
}

// ════════════════════════════════════════════════
// Tableau de bord : widgets persistants
// ════════════════════════════════════════════════

/// Renvoie le tableau de bord du projet, en le creant au besoin.
async fn ensure_dashboard(
    st: &AppState,
    project_id: Uuid,
    user_id: Uuid,
) -> Result<Dashboard, ApiError> {
    if let Some(d) = sqlx::query_as::<_, Dashboard>(
        "SELECT id, project_id, name, created_at, updated_at \
         FROM dashboards WHERE project_id = $1 ORDER BY created_at LIMIT 1",
    )
    .bind(project_id)
    .fetch_optional(&st.db)
    .await?
    {
        return Ok(d);
    }
    let d = sqlx::query_as::<_, Dashboard>(
        "INSERT INTO dashboards (project_id, user_id) VALUES ($1, $2) \
         RETURNING id, project_id, name, created_at, updated_at",
    )
    .bind(project_id)
    .bind(user_id)
    .fetch_one(&st.db)
    .await?;
    Ok(d)
}

async fn widgets_of(st: &AppState, dashboard_id: Uuid) -> Result<Vec<Widget>, ApiError> {
    Ok(sqlx::query_as::<_, Widget>(
        "SELECT id, dashboard_id, title, sql, viz, format, position, style, created_at, updated_at \
         FROM widgets WHERE dashboard_id = $1 ORDER BY position, created_at",
    )
    .bind(dashboard_id)
    .fetch_all(&st.db)
    .await?)
}

/// Tableau de bord + widgets + donnees fraiches de chaque widget.
/// Rouvrir un tableau de bord ne coute aucun appel IA : on rejoue le SQL stocke.
pub async fn dashboard_get(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    owned_project(&st, project_id, user.id).await?;
    let dash = ensure_dashboard(&st, project_id, user.id).await?;
    let widgets = widgets_of(&st, dash.id).await?;

    let mut out = Vec::with_capacity(widgets.len());
    for w in widgets {
        let data = engine::call_engine(
            &st,
            "/v1/warehouse/sql",
            &json!({ "project_id": project_id.to_string(), "sql": w.sql, "limit": 1000 }),
        )
        .await;
        let (result, error) = match data {
            Ok(v) => (Some(v), None),
            Err(e) => (None, Some(format!("{e}"))),
        };
        out.push(json!({ "widget": w, "data": result, "erreur": error }));
    }

    Ok(Json(json!({ "dashboard": dash, "widgets": out })))
}

/// Insere un widget a la fin du tableau de bord.
async fn insert_widget(
    st: &AppState,
    dashboard_id: Uuid,
    op: &Value,
) -> Result<Widget, ApiError> {
    let position: i32 = sqlx::query_scalar(
        "SELECT coalesce(max(position), -1) + 1 FROM widgets WHERE dashboard_id = $1",
    )
    .bind(dashboard_id)
    .fetch_one(&st.db)
    .await?;

    Ok(sqlx::query_as::<_, Widget>(
        "INSERT INTO widgets (dashboard_id, title, sql, viz, format, position, style) \
         VALUES ($1, $2, $3, $4, $5, $6, $7) \
         RETURNING id, dashboard_id, title, sql, viz, format, position, style, \
                   created_at, updated_at",
    )
    .bind(dashboard_id)
    .bind(op.get("titre").and_then(|v| v.as_str()).unwrap_or("Indicateur"))
    .bind(op.get("sql").and_then(|v| v.as_str()).unwrap_or_default())
    .bind(op.get("viz").and_then(|v| v.as_str()).unwrap_or("table"))
    .bind(op.get("format").and_then(|v| v.as_str()).unwrap_or("nombre"))
    .bind(position)
    .bind(op.get("style").cloned().filter(|s| s.is_object()))
    .fetch_one(&st.db)
    .await?)
}

#[derive(Deserialize)]
pub struct DashboardChatBody {
    pub message: String,
    #[serde(default)]
    pub history: Vec<Value>,
}

/// Edition du tableau de bord en langage naturel : ajout, modification ou
/// suppression d'indicateurs, appliques immediatement.
pub async fn dashboard_chat(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
    Json(b): Json<DashboardChatBody>,
) -> Result<Json<Value>, ApiError> {
    owned_project(&st, project_id, user.id).await?;
    quota::enforce(&st, user.id, "ai_query").await?;
    let key = ai_key(&st)?;

    let dash = ensure_dashboard(&st, project_id, user.id).await?;
    let widgets = widgets_of(&st, dash.id).await?;

    let res = engine::call_engine(
        &st,
        "/v1/warehouse/dashboard/edit",
        &json!({
            "project_id": project_id.to_string(),
            "message": b.message,
            "history": b.history,
            "widgets": widgets,
            "api_key": key,
        }),
    )
    .await?;
    quota::log(&st, user.id, "ai_query").await;

    // L'engine n'a renvoye que des operations dont le SQL s'execute : on applique.
    let mut applied = Vec::new();
    for op in res.get("operations").and_then(|v| v.as_array()).cloned().unwrap_or_default() {
        match op.get("action").and_then(|v| v.as_str()) {
            Some("add") => {
                let w = insert_widget(&st, dash.id, &op).await?;
                applied.push(json!({ "action": "add", "widget": w }));
            }
            Some("update") => {
                let Some(id) = op.get("widget_id").and_then(|v| v.as_str()).and_then(|s| s.parse::<Uuid>().ok())
                else {
                    continue;
                };
                let w = sqlx::query_as::<_, Widget>(
                    "UPDATE widgets SET title = coalesce($1, title), sql = coalesce($2, sql), \
                            viz = coalesce($3, viz), format = coalesce($4, format), \
                            style = coalesce(style, '{}'::jsonb) || coalesce($5, '{}'::jsonb), \
                            updated_at = now() \
                     WHERE id = $6 AND dashboard_id = $7 \
                     RETURNING id, dashboard_id, title, sql, viz, format, position, style, \
                               created_at, updated_at",
                )
                .bind(op.get("titre").and_then(|v| v.as_str()))
                .bind(op.get("sql").and_then(|v| v.as_str()))
                .bind(op.get("viz").and_then(|v| v.as_str()))
                .bind(op.get("format").and_then(|v| v.as_str()))
                // Fusion et non remplacement : « mets-la en orange » ne doit
                // pas effacer le cercle pose sur le pic au message precedent.
                .bind(op.get("style").cloned().filter(|s| s.is_object()))
                .bind(id)
                .bind(dash.id)
                .fetch_optional(&st.db)
                .await?;
                if let Some(w) = w {
                    applied.push(json!({ "action": "update", "widget": w }));
                }
            }
            Some("remove") => {
                let Some(id) = op.get("widget_id").and_then(|v| v.as_str()).and_then(|s| s.parse::<Uuid>().ok())
                else {
                    continue;
                };
                sqlx::query("DELETE FROM widgets WHERE id = $1 AND dashboard_id = $2")
                    .bind(id)
                    .bind(dash.id)
                    .execute(&st.db)
                    .await?;
                applied.push(json!({ "action": "remove", "widget_id": id }));
            }
            _ => {}
        }
    }

    Ok(Json(json!({
        "reponse": res.get("reponse").cloned().unwrap_or(Value::Null),
        "operations": applied,
        "rejetees": res.get("rejetees").cloned().unwrap_or(json!([])),
    })))
}

/// Premier tableau de bord : l'IA propose, l'utilisateur choisit.
/// Rien n'est enregistre ici — la selection passe par `dashboard_add`.
#[derive(Deserialize)]
pub struct ProposeBody {
    #[serde(default = "default_langue")]
    pub langue: String,
}

pub async fn dashboard_propose(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
    Json(b): Json<ProposeBody>,
) -> Result<Json<Value>, ApiError> {
    owned_project(&st, project_id, user.id).await?;
    quota::enforce(&st, user.id, "ai_query").await?;
    let key = ai_key(&st)?;
    let res = engine::call_engine(
        &st,
        "/v1/warehouse/kpi/propose",
        &json!({ "project_id": project_id.to_string(), "langue": b.langue, "api_key": key }),
    )
    .await?;
    quota::log(&st, user.id, "ai_query").await;
    Ok(Json(res))
}

#[derive(Deserialize)]
pub struct AddWidgetsBody {
    pub widgets: Vec<Value>,
    /// Remplace le tableau de bord existant au lieu d'y ajouter.
    #[serde(default)]
    pub replace: bool,
}

pub async fn dashboard_add(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
    Json(b): Json<AddWidgetsBody>,
) -> Result<Json<Value>, ApiError> {
    owned_project(&st, project_id, user.id).await?;
    let dash = ensure_dashboard(&st, project_id, user.id).await?;

    if b.replace {
        sqlx::query("DELETE FROM widgets WHERE dashboard_id = $1")
            .bind(dash.id)
            .execute(&st.db)
            .await?;
    }
    let mut created = Vec::new();
    for w in &b.widgets {
        created.push(insert_widget(&st, dash.id, w).await?);
    }
    Ok(Json(json!({ "widgets": created })))
}

#[derive(Deserialize)]
pub struct ReportBody {
    /// Consigne libre (« insiste sur les annulations »), facultative.
    #[serde(default)]
    pub demande: String,
    #[serde(default = "default_langue")]
    pub langue: String,
}

/// Rapport PDF du projet : etat des lieux, points d'attention, recommandations
/// et graphiques. Renvoie directement le document, pret a etre telecharge.
pub async fn report(
    State(st): State<AppState>,
    user: AuthUser,
    Path(project_id): Path<Uuid>,
    Json(b): Json<ReportBody>,
) -> Result<axum::response::Response, ApiError> {
    owned_project(&st, project_id, user.id).await?;
    quota::enforce(&st, user.id, "ai_query").await?;
    let key = ai_key(&st)?;

    let name: String = sqlx::query_scalar("SELECT name FROM projects WHERE id = $1")
        .bind(project_id)
        .fetch_one(&st.db)
        .await?;

    // Les indicateurs deja construits font foi ; l'engine en propose sinon.
    let dash = ensure_dashboard(&st, project_id, user.id).await?;
    let widgets = widgets_of(&st, dash.id).await?;

    let res = engine::call_engine(
        &st,
        "/v1/warehouse/report",
        &json!({
            "project_id": project_id.to_string(),
            "projet": name,
            "widgets": widgets,
            "demande": b.demande,
            "langue": b.langue,
            "api_key": key,
        }),
    )
    .await?;
    quota::log(&st, user.id, "ai_query").await;

    let encoded = res
        .get("pdf_base64")
        .and_then(|v| v.as_str())
        .ok_or_else(|| ApiError::Engine("rapport sans document".into()))?;

    use base64::Engine as _;
    let pdf = base64::engine::general_purpose::STANDARD
        .decode(encoded)
        .map_err(|e| ApiError::Engine(format!("document illisible: {e}")))?;

    // Nom de fichier : ASCII pour l'en-tete, sans quoi un titre accentue ou
    // arabe casserait le Content-Disposition.
    let slug = table_slug(&name);
    let entete = format!("attachment; filename=\"rapport_{slug}.pdf\"");

    use axum::response::IntoResponse;
    Ok((
        [
            (axum::http::header::CONTENT_TYPE, "application/pdf".to_string()),
            (axum::http::header::CONTENT_DISPOSITION, entete),
        ],
        pdf,
    )
        .into_response())
}

#[derive(Deserialize)]
pub struct UpdateWidgetBody {
    pub title: Option<String>,
    pub sql: Option<String>,
    pub viz: Option<String>,
    pub format: Option<String>,
    pub position: Option<i32>,
    /// Apparence complete ; remplace la precedente (l'editeur manuel montre
    /// l'etat courant, contrairement au chat qui procede par retouches).
    pub style: Option<Value>,
}

/// Edition manuelle d'un widget — le SQL reste modifiable a la main.
pub async fn widget_update(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
    Json(b): Json<UpdateWidgetBody>,
) -> Result<Json<Widget>, ApiError> {
    let w = sqlx::query_as::<_, Widget>(
        "UPDATE widgets w SET title = coalesce($1, w.title), sql = coalesce($2, w.sql), \
                viz = coalesce($3, w.viz), format = coalesce($4, w.format), \
                position = coalesce($5, w.position), style = coalesce($6, w.style), \
                updated_at = now() \
         FROM dashboards d \
         WHERE w.id = $7 AND w.dashboard_id = d.id AND d.user_id = $8 \
         RETURNING w.id, w.dashboard_id, w.title, w.sql, w.viz, w.format, w.position, \
                   w.style, w.created_at, w.updated_at",
    )
    .bind(b.title)
    .bind(b.sql)
    .bind(b.viz)
    .bind(b.format)
    .bind(b.position)
    .bind(b.style)
    .bind(id)
    .bind(user.id)
    .fetch_optional(&st.db)
    .await?
    .ok_or(ApiError::NotFound)?;
    Ok(Json(w))
}

pub async fn widget_delete(
    State(st): State<AppState>,
    user: AuthUser,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, ApiError> {
    let deleted = sqlx::query(
        "DELETE FROM widgets w USING dashboards d \
         WHERE w.id = $1 AND w.dashboard_id = d.id AND d.user_id = $2",
    )
    .bind(id)
    .bind(user.id)
    .execute(&st.db)
    .await?
    .rows_affected();
    if deleted == 0 {
        return Err(ApiError::NotFound);
    }
    Ok(StatusCode::NO_CONTENT)
}
