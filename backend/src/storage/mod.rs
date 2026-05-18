use sqlx::{sqlite::SqlitePoolOptions, SqlitePool, Row};
use std::sync::Arc;

pub struct Database {
    pub pool: SqlitePool,
}

impl Database {
    pub async fn new(db_url: &str) -> Result<Self, sqlx::Error> {
        // Set up connection pool with SQLite PRAGMAs for performance
        let pool = SqlitePoolOptions::new()
            .max_connections(10)
            .connect(db_url)
            .await?;

        // Enable Write-Ahead Logging (WAL) for highly concurrent reads/writes
        sqlx::query("PRAGMA journal_mode = WAL;")
            .execute(&pool)
            .await?;
        
        sqlx::query("PRAGMA synchronous = NORMAL;")
            .execute(&pool)
            .await?;

        // Initialize schema (Memory context or agents context can live here later)
        let _ = sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS task_graph (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                objective TEXT NOT NULL,
                plan TEXT,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS execution_history (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                command TEXT,
                stdout TEXT,
                diff TEXT,
                evidence_path TEXT,
                status TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(task_id) REFERENCES task_graph(id)
            );
            "#,
        )
        .execute(&pool)
        .await?;

        // Initialize base tables if they don't exist
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );"
        )
        .execute(&pool)
        .await?;

        Ok(Self { pool })
    }

    pub async fn log_event(&self, event_type: &str, payload: &str) -> Result<(), sqlx::Error> {
        sqlx::query("INSERT INTO audit_logs (event_type, payload) VALUES (?, ?)")
            .bind(event_type)
            .bind(payload)
            .execute(&self.pool)
            .await?;
        Ok(())
    }
}
