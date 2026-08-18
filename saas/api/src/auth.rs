use axum::{
    async_trait,
    extract::{FromRequestParts, Request, State},
    http::{header, request::Parts, HeaderMap},
    middleware::Next,
    response::Response,
};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use serde::Deserialize;
use uuid::Uuid;

use crate::{error::ApiError, state::AppState};

/// Utilisateur authentifie, injecte dans les extensions de la requete.
#[derive(Clone, Debug)]
pub struct AuthUser {
    pub id: Uuid,
    pub email: Option<String>,
}

#[derive(Deserialize)]
struct Claims {
    sub: String,
    email: Option<String>,
    #[allow(dead_code)]
    exp: usize,
}

/// Middleware : authentifie, upsert le user en base, injecte AuthUser.
pub async fn auth_middleware(
    State(state): State<AppState>,
    mut req: Request,
    next: Next,
) -> Result<Response, ApiError> {
    let user = authenticate(&state, req.headers())?;

    if state.cfg.auth_mode == "local" {
        // Le compte a ete cree a l'inscription : on verifie seulement qu'il
        // existe toujours. Un upsert ecraserait le nom et l'empreinte, et
        // ressusciterait un compte supprime a partir d'un jeton encore valide.
        let existe: Option<Uuid> = sqlx::query_scalar("SELECT id FROM users WHERE id = $1")
            .bind(user.id)
            .fetch_optional(&state.db)
            .await?;
        if existe.is_none() {
            return Err(ApiError::Unauthorized);
        }
    } else {
        // Modes dev et Supabase : l'identite fait foi ailleurs, on reflete
        // l'utilisateur en base au premier appel.
        sqlx::query(
            "INSERT INTO users (id, email) VALUES ($1, $2) \
             ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, updated_at = now()",
        )
        .bind(user.id)
        .bind(user.email.as_deref())
        .execute(&state.db)
        .await?;
    }

    req.extensions_mut().insert(user);
    Ok(next.run(req).await)
}

/// Extrait le jeton porteur de l'en-tete Authorization.
fn jeton(headers: &HeaderMap) -> Result<&str, ApiError> {
    headers
        .get(header::AUTHORIZATION)
        .and_then(|h| h.to_str().ok())
        .and_then(|s| s.strip_prefix("Bearer "))
        .ok_or(ApiError::Unauthorized)
}

fn authenticate(state: &AppState, headers: &HeaderMap) -> Result<AuthUser, ApiError> {
    // Mode local : jeton emis et signe par cette api.
    if state.cfg.auth_mode == "local" {
        let mut validation = Validation::new(Algorithm::HS256);
        validation.set_issuer(&["datavox"]);
        // L'expiration est verifiee par defaut ; on l'explicite pour que le
        // jour ou quelqu'un touche a cette validation, l'intention soit claire.
        validation.validate_exp = true;

        let data = decode::<Claims>(
            jeton(headers)?,
            &DecodingKey::from_secret(state.cfg.auth_secret.as_bytes()),
            &validation,
        )
        .map_err(|_| ApiError::Unauthorized)?;

        let id = Uuid::parse_str(&data.claims.sub).map_err(|_| ApiError::Unauthorized)?;
        return Ok(AuthUser {
            id,
            email: data.claims.email,
        });
    }

    // Mode dev : pas de Supabase requis, on simule via un en-tete.
    if state.cfg.auth_mode == "dev" {
        let raw = headers
            .get("x-dev-user-id")
            .and_then(|h| h.to_str().ok())
            .ok_or(ApiError::Unauthorized)?;
        let id = Uuid::parse_str(raw)
            .map_err(|_| ApiError::BadRequest("x-dev-user-id invalide (UUID attendu)".into()))?;
        let email = headers
            .get("x-dev-email")
            .and_then(|h| h.to_str().ok())
            .map(|s| s.to_string());
        return Ok(AuthUser { id, email });
    }

    // Mode prod : verification du JWT Supabase (HS256).
    let mut validation = Validation::new(Algorithm::HS256);
    validation.set_audience(&["authenticated"]);

    let data = decode::<Claims>(
        jeton(headers)?,
        &DecodingKey::from_secret(state.cfg.supabase_jwt_secret.as_bytes()),
        &validation,
    )
    .map_err(|_| ApiError::Unauthorized)?;

    let id = Uuid::parse_str(&data.claims.sub).map_err(|_| ApiError::Unauthorized)?;
    Ok(AuthUser {
        id,
        email: data.claims.email,
    })
}

#[async_trait]
impl<S: Send + Sync> FromRequestParts<S> for AuthUser {
    type Rejection = ApiError;

    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        parts
            .extensions
            .get::<AuthUser>()
            .cloned()
            .ok_or(ApiError::Unauthorized)
    }
}
