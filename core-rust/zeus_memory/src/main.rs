use axum::{
    routing::{get, post},
    Json, Router, extract::State,
};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, RwLock};
use zeus_memory::VectorMemoryRust;

#[derive(Serialize, Deserialize)]
struct MemoryEntry {
    key: String,
    vector: Vec<f32>,
}

#[derive(Serialize, Deserialize)]
struct QueryRequest {
    vector: Vec<f32>,
    top_k: usize,
}

struct AppState {
    manager: RwLock<VectorMemoryRust>,
}

#[tokio::main]
async fn main() {
    let storage_path = "data/neural_vectors.bin".to_string();
    let manager = VectorMemoryRust::new_rust(storage_path);
    let state = Arc::new(AppState {
        manager: RwLock::new(manager),
    });

    let app = Router::new()
        .route("/health", get(health_check))
        .route("/add", post(add_vector))
        .route("/query", post(query_vector))
        .route("/save", post(save_memory))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("127.0.0.1:8082").await.unwrap();
    println!("🧠 ZEUS Memory Service (Rust Microservice) rodando em http://127.0.0.1:8082");
    axum::serve(listener, app).await.unwrap();
}

async fn health_check() -> &'static str {
    "Memory Service Operational"
}

async fn add_vector(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<MemoryEntry>,
) -> Json<serde_json::Value> {
    let mut manager = state.manager.write().unwrap();
    manager.add_vector_rust(payload.key, payload.vector);
    Json(serde_json::json!({"status": "success"}))
}

async fn query_vector(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<QueryRequest>,
) -> Json<Vec<(String, f32)>> {
    let manager = state.manager.read().unwrap();
    let results = manager.find_similar_rust(&payload.vector, payload.top_k);
    Json(results)
}

async fn save_memory(
    State(state): State<Arc<AppState>>,
) -> Json<serde_json::Value> {
    let manager = state.manager.read().unwrap();
    match manager.save_rust() {
        Ok(_) => Json(serde_json::json!({"status": "saved"})),
        Err(e) => Json(serde_json::json!({"status": "error", "message": e.to_string()})),
    }
}
