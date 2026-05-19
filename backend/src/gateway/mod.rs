use crate::{events::SystemEvent, llm::LlmRouter, state::AppState};
use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        State,
    },
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use futures::{sink::SinkExt, stream::StreamExt};
use serde::Deserialize;
use std::sync::Arc;

#[derive(Deserialize)]
pub struct ApprovalPayload {
    pub command_id: String,
}

#[derive(Deserialize)]
pub struct RollbackPayload {
    pub relative_path: String,
    pub backup_path: String,
}

#[derive(Deserialize)]
pub struct PatchPayload {
    pub relative_path: String,
    pub content: String,
}

pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/ws", get(ws_handler))
        .route("/api/approve", post(approve_handler))
        .route("/api/deny", post(deny_handler))
        .route("/api/patch", post(patch_handler))
        .route("/api/rollback", post(rollback_handler))
        .with_state(state)
}

async fn approve_handler(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<ApprovalPayload>,
) -> impl IntoResponse {
    if let Some(cmd) = state.approvals.approve(&payload.command_id) {
        let state_clone = state.clone();
        let cmd_clone = cmd.clone();
        let cmd_id = payload.command_id.clone();
        tokio::spawn(async move {
            let _ = state_clone.executor.execute(&cmd_id, &cmd_clone).await;
        });
        (axum::http::StatusCode::OK, "Approved")
    } else {
        (axum::http::StatusCode::NOT_FOUND, "Not Found")
    }
}

async fn deny_handler(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<ApprovalPayload>,
) -> impl IntoResponse {
    state.approvals.deny(&payload.command_id);
    (axum::http::StatusCode::OK, "Denied")
}

async fn patch_handler(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<PatchPayload>,
) -> impl IntoResponse {
    match state
        .patcher
        .apply_patch(&payload.relative_path, &payload.content)
        .await
    {
        Ok(diff) => (axum::http::StatusCode::OK, diff),
        Err(error) => (axum::http::StatusCode::BAD_REQUEST, error),
    }
}

async fn rollback_handler(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<RollbackPayload>,
) -> impl IntoResponse {
    match state
        .patcher
        .rollback(&payload.relative_path, &payload.backup_path)
        .await
    {
        Ok(_) => (axum::http::StatusCode::OK, "Rollback successful"),
        Err(_) => (
            axum::http::StatusCode::INTERNAL_SERVER_ERROR,
            "Rollback failed",
        ),
    }
}

async fn ws_handler(ws: WebSocketUpgrade, State(state): State<Arc<AppState>>) -> impl IntoResponse {
    ws.on_upgrade(|socket| handle_socket(socket, state))
}

async fn handle_socket(socket: WebSocket, state: Arc<AppState>) {
    let (mut sender, mut receiver) = socket.split();

    // Subscribe to the global Event Bus
    let mut rx = state.event_bus.subscribe();

    // Task: Forward events from EventBus → WebSocket client
    let mut send_task = tokio::spawn(async move {
        while let Ok(event) = rx.recv().await {
            if let Ok(msg) = serde_json::to_string(&event) {
                if sender.send(Message::Text(msg)).await.is_err() {
                    break;
                }
            }
        }
    });

    // Task: Receive prompts from WS client → LLM Router → stream response back
    let state_recv = Arc::clone(&state);
    let mut recv_task = tokio::spawn(async move {
        use futures::pin_mut;

        while let Some(Ok(Message::Text(text))) = receiver.next().await {
            tracing::info!("WS prompt received: {}", text);

            let llm = LlmRouter::new(Arc::clone(&state_recv));
            let stream = llm.process_prompt(&text);
            pin_mut!(stream);

            while let Some(chunk) = stream.next().await {
                let _ = state_recv
                    .event_bus
                    .publish(SystemEvent::MessageStreamChunk {
                        id: "ws_stream".to_string(),
                        chunk,
                    });
            }
        }
    });

    tokio::select! {
        _ = (&mut send_task) => recv_task.abort(),
        _ = (&mut recv_task) => send_task.abort(),
    };

    tracing::info!("WebSocket disconnected");
}
