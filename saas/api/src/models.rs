use chrono::{DateTime, Utc};
use serde::Serialize;
use sqlx::FromRow;
use uuid::Uuid;

#[derive(Debug, Serialize, FromRow)]
pub struct User {
    pub id: Uuid,
    pub email: Option<String>,
    pub tier: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, FromRow)]
pub struct Workspace {
    pub id: Uuid,
    pub user_id: Uuid,
    pub name: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, FromRow)]
pub struct Project {
    pub id: Uuid,
    pub user_id: Uuid,
    pub workspace_id: Uuid,
    pub name: String,
    pub description: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, FromRow)]
pub struct Dataset {
    pub id: Uuid,
    pub project_id: Uuid,
    pub user_id: Uuid,
    pub filename: String,
    pub row_count: Option<i32>,
    pub col_count: Option<i32>,
    pub status: String,
    pub profile: Option<serde_json::Value>,
    pub created_at: DateTime<Utc>,
}

/// Une source du projet, vue depuis l'entrepot (une table DuckDB).
#[derive(Debug, Serialize, FromRow)]
pub struct DatasetSource {
    pub id: Uuid,
    pub project_id: Uuid,
    pub filename: String,
    pub table_name: Option<String>,
    pub column_map: Option<serde_json::Value>,
    pub row_count: Option<i32>,
    pub col_count: Option<i32>,
    pub status: String,
    pub profile: Option<serde_json::Value>,
    pub ingested_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, FromRow)]
pub struct Dashboard {
    pub id: Uuid,
    pub project_id: Uuid,
    pub name: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, FromRow)]
pub struct Widget {
    pub id: Uuid,
    pub dashboard_id: Uuid,
    pub title: String,
    pub sql: String,
    pub viz: String,
    pub format: String,
    pub position: i32,
    /// Apparence : couleur, mise en evidence des extremes, etiquettes.
    /// Separee du SQL — habiller un indicateur ne le recalcule pas.
    pub style: Option<serde_json::Value>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, FromRow)]
pub struct Job {
    pub id: Uuid,
    pub user_id: Uuid,
    pub project_id: Option<Uuid>,
    pub dataset_id: Option<Uuid>,
    pub kind: String,
    pub status: String,
    pub payload: serde_json::Value,
    pub result: Option<serde_json::Value>,
    pub error: Option<String>,
    pub created_at: DateTime<Utc>,
}
