pub mod billing;
// Nomme `comptes` et non `auth` : `crate::auth` porte deja le middleware
// d'authentification, deux modules `auth` preteraient a confusion.
pub mod comptes;
pub mod datasets;
pub mod health;
pub mod jobs;
pub mod me;
pub mod projects;
pub mod warehouse;
pub mod workspaces;

use axum::{
    extract::DefaultBodyLimit,
    http::HeaderValue,
    middleware,
    routing::{get, patch, post},
    Router,
};
use tower_http::cors::{Any, CorsLayer};

use crate::{auth, state::AppState};

pub fn router(state: AppState) -> Router {
    let origin = state
        .cfg
        .allowed_origin
        .parse::<HeaderValue>()
        .unwrap_or_else(|_| HeaderValue::from_static("http://localhost:3000"));

    let cors = CorsLayer::new()
        .allow_origin(origin)
        .allow_methods(Any)
        .allow_headers(Any)
        // Sans cette exposition, le navigateur masque l'en-tete au JavaScript
        // en requete inter-origine : le rapport serait enregistre sous un nom
        // generique au lieu de porter celui du projet.
        .expose_headers([axum::http::header::CONTENT_DISPOSITION]);

    let protected = Router::new()
        .route("/v1/me", get(me::me))
        .route("/v1/workspaces", get(workspaces::list).post(workspaces::create))
        .route("/v1/workspaces/:id", patch(workspaces::rename).delete(workspaces::remove))
        .route("/v1/projects", get(projects::list).post(projects::create))
        .route("/v1/projects/:id", get(projects::get_one).delete(projects::remove))
        .route("/v1/projects/:id/datasets", get(projects::list_datasets).post(projects::create_dataset))
        .route("/v1/datasets/:id/clean/plan", post(datasets::clean_plan))
        .route("/v1/datasets/:id/clean/apply", post(datasets::clean_apply))
        .route("/v1/datasets/:id/analyze/axes", post(datasets::analyze_axes))
        .route("/v1/datasets/:id/analyze/correlations", post(datasets::analyze_correlations))
        .route("/v1/datasets/:id/analyze/segment", post(datasets::analyze_segment))
        .route("/v1/datasets/:id/analyze/time", post(datasets::analyze_time))
        .route("/v1/datasets/:id/doc/dictionary", post(datasets::doc_dictionary))
        .route("/v1/datasets/:id/doc/warehouse", post(datasets::doc_warehouse))
        .route("/v1/datasets/:id/doc/export", post(datasets::doc_export))
        .route("/v1/datasets/:id/kpi/suggest", post(datasets::kpi_suggest))
        .route("/v1/datasets/:id/kpi/compute", post(datasets::kpi_compute))
        .route("/v1/datasets/:id/values", post(datasets::column_values))
        .route("/v1/datasets/:id/chat", post(datasets::chat))
        // ── Entrepot analytique : ETL, SQL, chat, tableau de bord ──
        .route("/v1/files/inspect", post(warehouse::inspect_file))
        .route("/v1/files/diagnose", post(warehouse::diagnose_file))
        .route("/v1/projects/:id/sources", get(warehouse::list_sources).post(warehouse::ingest))
        .route("/v1/projects/:id/warehouse/schema", get(warehouse::schema))
        .route("/v1/projects/:id/warehouse/sql", post(warehouse::run_sql))
        .route("/v1/projects/:id/chat", post(warehouse::chat))
        .route("/v1/projects/:id/dashboard", get(warehouse::dashboard_get).post(warehouse::dashboard_add))
        .route("/v1/projects/:id/dashboard/chat", post(warehouse::dashboard_chat))
        .route("/v1/projects/:id/dashboard/propose", post(warehouse::dashboard_propose))
        .route("/v1/projects/:id/report", post(warehouse::report))
        .route("/v1/sources/:id/refresh/check", post(warehouse::refresh_check))
        .route("/v1/sources/:id/refresh", post(warehouse::refresh_apply))
        .route("/v1/widgets/:id", patch(warehouse::widget_update).delete(warehouse::widget_delete))
        .route("/v1/jobs/:id", get(jobs::get_one))
        // Session courante et changement de mot de passe : declares AVANT
        // route_layer, sinon ils echapperaient au middleware — `route_layer`
        // ne couvre que les routes deja enregistrees.
        .route("/v1/auth/me", get(comptes::me))
        .route("/v1/auth/password", post(comptes::change_password))
        .route_layer(middleware::from_fn_with_state(
            state.clone(),
            auth::auth_middleware,
        ));

    // Points d'entree publics : s'inscrire et se connecter ne peuvent pas
    // exiger d'etre deja authentifie.
    let public = Router::new()
        .route("/health", get(health::health))
        .route("/v1/billing/plans", get(billing::plans))
        .route("/v1/auth/register", post(comptes::register))
        .route("/v1/auth/login", post(comptes::login));

    public
        .merge(protected)
        // axum plafonne les corps de requete a 2 Mo par defaut. Un classeur
        // voyage encode en base64 (+33 %) : la limite d'origine refusait tout
        // fichier de plus de ~1,5 Mo, soit un Excel de 50 000 lignes.
        //
        // Le fichier reste tenu EN MEMOIRE de bout en bout (api, Postgres,
        // engine) : ce plafond est donc un vrai garde-fou, pas une formalite.
        // Au-dela, la reponse est un object storage avec envoi direct, deja
        // inscrit dans la feuille de route.
        .layer(DefaultBodyLimit::max(LIMITE_CORPS))
        .layer(cors)
        .with_state(state)
}

/// Taille maximale d'un corps de requete : 32 Mo, soit environ 24 Mo de
/// fichier une fois l'encodage base64 deduit.
pub const LIMITE_CORPS: usize = 32 * 1024 * 1024;
