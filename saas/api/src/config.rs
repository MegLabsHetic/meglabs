use std::env;

#[derive(Clone)]
pub struct Config {
    pub bind_addr: String,
    pub database_url: String,
    pub engine_url: String,
    /// "local" (comptes geres ici), "dev" (en-tete x-dev-user-id), "prod" (Supabase).
    pub auth_mode: String,
    /// Secret de signature des jetons emis par CETTE api (mode "local").
    pub auth_secret: String,
    pub supabase_jwt_secret: String,
    pub allowed_origin: String,
    /// Palier attribue aux nouveaux comptes. Une instance auto-hebergee n'a
    /// aucune raison de brider son proprietaire : mettre DEFAULT_TIER=enterprise.
    pub default_tier: String,
    /// Cle Anthropic de la plateforme, transmise a l'engine pour les operations IA.
    /// Robustesse : a remplacer par une cle par tenant (voir roadmap).
    pub anthropic_api_key: String,
}

impl Config {
    pub fn from_env() -> anyhow::Result<Self> {
        let auth_mode = env::var("AUTH_MODE").unwrap_or_else(|_| "local".into());
        let auth_secret = env::var("AUTH_SECRET").unwrap_or_default();

        // Un secret vide en mode local signerait des jetons que n'importe qui
        // pourrait forger : on refuse de demarrer plutot que de faire semblant
        // de proteger les comptes.
        if auth_mode == "local" && auth_secret.len() < 32 {
            anyhow::bail!(
                "AUTH_SECRET doit faire au moins 32 caracteres en mode local \
                 (generez-en un avec : openssl rand -hex 32)"
            );
        }

        Ok(Self {
            bind_addr: env::var("BIND_ADDR").unwrap_or_else(|_| "0.0.0.0:8080".into()),
            database_url: env::var("DATABASE_URL")
                .map_err(|_| anyhow::anyhow!("DATABASE_URL manquante"))?,
            engine_url: env::var("ENGINE_URL").unwrap_or_else(|_| "http://localhost:8000".into()),
            auth_mode,
            auth_secret,
            supabase_jwt_secret: env::var("SUPABASE_JWT_SECRET").unwrap_or_default(),
            allowed_origin: env::var("ALLOWED_ORIGIN")
                .unwrap_or_else(|_| "http://localhost:3000".into()),
            default_tier: env::var("DEFAULT_TIER").unwrap_or_else(|_| "free".into()),
            anthropic_api_key: env::var("ANTHROPIC_API_KEY").unwrap_or_default(),
        })
    }
}

/// Limites journalieres par palier : (uploads, requetes IA). -1 = illimite.
pub fn tier_limits(tier: &str) -> (i64, i64) {
    match tier {
        "pro" => (50, 200),
        "enterprise" => (-1, -1),
        _ => (3, 10),
    }
}
