use axum::Json;
use serde_json::{json, Value};

/// Paliers d'abonnement (statique). Le branchement Stripe viendra remplir
/// les tables subscriptions ; l'enforcement des quotas est deja actif.
pub async fn plans() -> Json<Value> {
    Json(json!({
        "plans": [
            { "tier": "free", "name": "Gratuit", "price_monthly": 0,
              "uploads_per_day": 3, "ai_queries_per_day": 10 },
            { "tier": "pro", "name": "Pro", "price_monthly": 29,
              "uploads_per_day": 50, "ai_queries_per_day": 200 },
            { "tier": "enterprise", "name": "Enterprise", "price_monthly": 99,
              "uploads_per_day": -1, "ai_queries_per_day": -1 }
        ]
    }))
}
