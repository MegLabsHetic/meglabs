//! Authentification native : inscription, connexion, jeton.
//!
//! Le mot de passe n'est jamais stocke ni journalise : seule une empreinte
//! Argon2id est conservee. Le jeton est un JWT signe par CE serveur — aucun
//! fournisseur externe n'est requis pour se connecter.

use argon2::{Argon2, PasswordHash, PasswordHasher, PasswordVerifier};
use axum::{extract::State, http::StatusCode, Json};
use jsonwebtoken::{encode, EncodingKey, Header};
use password_hash::{rand_core::OsRng, SaltString};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use uuid::Uuid;

use crate::{auth::AuthUser, error::ApiError, state::AppState};

/// Duree de validite du jeton. Assez longue pour ne pas deconnecter en pleine
/// analyse, assez courte pour qu'un jeton vole ne serve pas indefiniment.
const DUREE_JETON_JOURS: i64 = 7;

const MIN_MOT_DE_PASSE: usize = 8;

#[derive(Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub email: Option<String>,
    pub exp: usize,
    pub iss: String,
}

#[derive(Deserialize)]
pub struct Inscription {
    pub email: String,
    pub password: String,
    pub name: Option<String>,
}

#[derive(Deserialize)]
pub struct Connexion {
    pub email: String,
    pub password: String,
}

/// Normalise l'e-mail : la casse et les espaces ne doivent pas creer deux
/// comptes distincts pour la meme personne.
fn normaliser(email: &str) -> String {
    email.trim().to_lowercase()
}

fn email_plausible(email: &str) -> bool {
    let Some((locale, domaine)) = email.split_once('@') else {
        return false;
    };
    !locale.is_empty() && domaine.contains('.') && !domaine.starts_with('.')
        && !domaine.ends_with('.') && !email.contains(char::is_whitespace)
}

fn secret(st: &AppState) -> Result<&str, ApiError> {
    if st.cfg.auth_secret.is_empty() {
        return Err(ApiError::Internal("AUTH_SECRET non configure".into()));
    }
    Ok(&st.cfg.auth_secret)
}

fn emettre_jeton(st: &AppState, id: Uuid, email: &str) -> Result<String, ApiError> {
    let exp = chrono::Utc::now() + chrono::Duration::days(DUREE_JETON_JOURS);
    let claims = Claims {
        sub: id.to_string(),
        email: Some(email.to_string()),
        exp: exp.timestamp() as usize,
        iss: "datavox".into(),
    };
    encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(secret(st)?.as_bytes()),
    )
    .map_err(|e| ApiError::Internal(format!("emission du jeton: {e}")))
}

fn reponse_session(jeton: String, id: Uuid, email: &str, name: Option<String>) -> Json<Value> {
    Json(json!({
        "token": jeton,
        "user": { "id": id, "email": email, "name": name },
    }))
}

// ════════════════════════════════════════════════
// Inscription
// ════════════════════════════════════════════════
pub async fn register(
    State(st): State<AppState>,
    Json(body): Json<Inscription>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    let email = normaliser(&body.email);
    if !email_plausible(&email) {
        return Err(ApiError::BadRequest("adresse e-mail invalide".into()));
    }
    if body.password.chars().count() < MIN_MOT_DE_PASSE {
        return Err(ApiError::BadRequest(format!(
            "le mot de passe doit faire au moins {MIN_MOT_DE_PASSE} caracteres"
        )));
    }

    let deja_pris: Option<Uuid> = sqlx::query_scalar(
        "SELECT id FROM users WHERE lower(email) = $1 AND password_hash IS NOT NULL",
    )
    .bind(&email)
    .fetch_optional(&st.db)
    .await?;
    if deja_pris.is_some() {
        return Err(ApiError::BadRequest("un compte existe deja avec cet e-mail".into()));
    }

    // Le sel est tire aleatoirement et range dans l'empreinte : deux comptes
    // partageant le meme mot de passe ont des empreintes differentes.
    let sel = SaltString::generate(&mut OsRng);
    let empreinte = Argon2::default()
        .hash_password(body.password.as_bytes(), &sel)
        .map_err(|e| ApiError::Internal(format!("hachage: {e}")))?
        .to_string();

    let id = Uuid::new_v4();
    let nom = body.name.map(|n| n.trim().to_string()).filter(|n| !n.is_empty());

    sqlx::query(
        "INSERT INTO users (id, email, name, password_hash, tier, last_login_at) \
         VALUES ($1, $2, $3, $4, $5, now())",
    )
    .bind(id)
    .bind(&email)
    .bind(&nom)
    .bind(&empreinte)
    // Palier configurable : une instance personnelle n'a pas a brider son
    // proprietaire avec des quotas penses pour une offre commerciale.
    .bind(&st.cfg.default_tier)
    .execute(&st.db)
    .await?;

    let jeton = emettre_jeton(&st, id, &email)?;
    Ok((StatusCode::CREATED, reponse_session(jeton, id, &email, nom)))
}

// ════════════════════════════════════════════════
// Connexion
// ════════════════════════════════════════════════
pub async fn login(
    State(st): State<AppState>,
    Json(body): Json<Connexion>,
) -> Result<Json<Value>, ApiError> {
    let email = normaliser(&body.email);

    let compte: Option<(Uuid, String, Option<String>)> = sqlx::query_as(
        "SELECT id, password_hash, name FROM users \
         WHERE lower(email) = $1 AND password_hash IS NOT NULL",
    )
    .bind(&email)
    .fetch_optional(&st.db)
    .await?;

    // Message identique que l'e-mail soit inconnu ou le mot de passe faux :
    // distinguer les deux revelerait quelles adresses sont enregistrees.
    let refus = || ApiError::Unauthorized;

    let Some((id, empreinte, nom)) = compte else {
        // On hache tout de meme une valeur bidon : sans cela, le temps de
        // reponse trahirait l'existence du compte.
        let sel = SaltString::generate(&mut OsRng);
        let _ = Argon2::default().hash_password(body.password.as_bytes(), &sel);
        return Err(refus());
    };

    let attendue = PasswordHash::new(&empreinte).map_err(|_| refus())?;
    Argon2::default()
        .verify_password(body.password.as_bytes(), &attendue)
        .map_err(|_| refus())?;

    sqlx::query("UPDATE users SET last_login_at = now() WHERE id = $1")
        .bind(id)
        .execute(&st.db)
        .await?;

    let jeton = emettre_jeton(&st, id, &email)?;
    Ok(reponse_session(jeton, id, &email, nom))
}

// ════════════════════════════════════════════════
// Session courante
// ════════════════════════════════════════════════
pub async fn me(State(st): State<AppState>, user: AuthUser) -> Result<Json<Value>, ApiError> {
    let ligne: Option<(Option<String>, Option<String>, String)> =
        sqlx::query_as("SELECT email, name, tier FROM users WHERE id = $1")
            .bind(user.id)
            .fetch_optional(&st.db)
            .await?;
    let (email, name, tier) = ligne.ok_or(ApiError::NotFound)?;
    Ok(Json(json!({ "id": user.id, "email": email, "name": name, "tier": tier })))
}

#[derive(Deserialize)]
pub struct ChangementMotDePasse {
    pub ancien: String,
    pub nouveau: String,
}

pub async fn change_password(
    State(st): State<AppState>,
    user: AuthUser,
    Json(body): Json<ChangementMotDePasse>,
) -> Result<StatusCode, ApiError> {
    if body.nouveau.chars().count() < MIN_MOT_DE_PASSE {
        return Err(ApiError::BadRequest(format!(
            "le mot de passe doit faire au moins {MIN_MOT_DE_PASSE} caracteres"
        )));
    }

    let empreinte: Option<String> =
        sqlx::query_scalar("SELECT password_hash FROM users WHERE id = $1")
            .bind(user.id)
            .fetch_optional(&st.db)
            .await?
            .flatten();
    let empreinte = empreinte.ok_or(ApiError::BadRequest(
        "ce compte n'utilise pas de mot de passe".into(),
    ))?;

    let actuelle = PasswordHash::new(&empreinte).map_err(|_| ApiError::Unauthorized)?;
    Argon2::default()
        .verify_password(body.ancien.as_bytes(), &actuelle)
        .map_err(|_| ApiError::Unauthorized)?;

    let sel = SaltString::generate(&mut OsRng);
    let nouvelle = Argon2::default()
        .hash_password(body.nouveau.as_bytes(), &sel)
        .map_err(|e| ApiError::Internal(format!("hachage: {e}")))?
        .to_string();

    sqlx::query("UPDATE users SET password_hash = $1, updated_at = now() WHERE id = $2")
        .bind(&nouvelle)
        .bind(user.id)
        .execute(&st.db)
        .await?;

    Ok(StatusCode::NO_CONTENT)
}
