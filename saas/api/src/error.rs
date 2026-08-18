use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;

#[derive(Debug)]
pub enum ApiError {
    Unauthorized,
    Forbidden,
    NotFound,
    BadRequest(String),
    TooManyRequests(String),
    Engine(String),
    Db(sqlx::Error),
    Internal(String),
}

impl std::fmt::Display for ApiError {
    /// Message destine aux journaux et aux erreurs remontees widget par widget
    /// (un widget en echec affiche sa raison sans casser le tableau de bord).
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ApiError::Unauthorized => write!(f, "non authentifie"),
            ApiError::Forbidden => write!(f, "acces refuse"),
            ApiError::NotFound => write!(f, "introuvable"),
            ApiError::BadRequest(m)
            | ApiError::TooManyRequests(m)
            | ApiError::Engine(m)
            | ApiError::Internal(m) => write!(f, "{m}"),
            ApiError::Db(e) => write!(f, "erreur base de donnees: {e}"),
        }
    }
}

impl std::error::Error for ApiError {}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (code, msg) = match self {
            ApiError::Unauthorized => (StatusCode::UNAUTHORIZED, "unauthorized".to_string()),
            ApiError::Forbidden => (StatusCode::FORBIDDEN, "forbidden".to_string()),
            ApiError::NotFound => (StatusCode::NOT_FOUND, "not_found".to_string()),
            ApiError::BadRequest(m) => (StatusCode::BAD_REQUEST, m),
            ApiError::TooManyRequests(m) => (StatusCode::TOO_MANY_REQUESTS, m),
            ApiError::Engine(m) => (StatusCode::BAD_GATEWAY, m),
            ApiError::Db(e) => {
                tracing::error!("db error: {e}");
                (StatusCode::INTERNAL_SERVER_ERROR, "database_error".to_string())
            }
            ApiError::Internal(m) => {
                tracing::error!("internal: {m}");
                (StatusCode::INTERNAL_SERVER_ERROR, "internal_error".to_string())
            }
        };
        (code, Json(json!({ "error": msg }))).into_response()
    }
}

impl From<sqlx::Error> for ApiError {
    fn from(e: sqlx::Error) -> Self {
        match e {
            sqlx::Error::RowNotFound => ApiError::NotFound,
            other => ApiError::Db(other),
        }
    }
}

impl From<reqwest::Error> for ApiError {
    /// Le detail technique part dans les journaux, pas a l'ecran : l'adresse
    /// interne du moteur et le nom de la variante Rust n'apprennent rien a
    /// l'utilisateur, qui voit ce message tel quel dans le suivi de tache.
    fn from(e: reqwest::Error) -> Self {
        tracing::error!("appel engine echoue: {e}");
        if e.is_connect() || e.is_timeout() {
            ApiError::Engine("le moteur d'analyse est injoignable".into())
        } else {
            ApiError::Engine("le moteur d'analyse a renvoye une reponse inattendue".into())
        }
    }
}
