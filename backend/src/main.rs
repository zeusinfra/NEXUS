mod events;
mod state;
mod gateway;
mod workers;
mod telemetry;
mod agents { pub mod mod_rs { } }
mod memory { pub mod mod_rs { } }
mod approvals;
mod execution;
mod llm;
mod storage;
mod filesystem;
mod streaming { pub mod mod_rs { } }
mod ui_bridge { pub mod mod_rs { } }

use std::sync::Arc;
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;

use crate::storage::Database;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. Initialize observability
    telemetry::init_tracing();
    tracing::info!("Starting NEXUS Cognitive Backend");

    // 2. Initialize the Event Bus
    let event_bus = events::EventBus::new(1024);

    // 3. Initialize Storage Engine (SQLite WAL)
    let db = Database::new("sqlite:nexus_backend.db?mode=rwc").await?;
    let db = Arc::new(db);

    // 4. Initialize Execution Engines
    let approvals = Arc::new(approvals::ApprovalEngine::new(event_bus.clone()));
    let executor = Arc::new(execution::command::CommandExecutor::new(event_bus.clone()));
    let task_graph = Arc::new(execution::graph::TaskGraphEngine::new(event_bus.clone(), Arc::clone(&db)));
    let patcher = Arc::new(execution::patch::FilePatchEngine::new(event_bus.clone(), "."));
    let test_runner = Arc::new(execution::test::TestRunner::new(event_bus.clone()));

    // 5. Assemble Global State
    let app_state = Arc::new(state::AppState::new(
        event_bus,
        db,
        approvals,
        executor,
        task_graph,
        patcher,
        test_runner,
    ));

    // 6. Start Filesystem Watcher
    filesystem::start_watcher(Arc::clone(&app_state), ".");

    // 7. Start Background Workers
    workers::start_background_workers(Arc::clone(&app_state));

    // 8. Setup HTTP/WebSocket Router
    let app = gateway::router(Arc::clone(&app_state))
        .layer(CorsLayer::permissive());

    // 9. Bind and Serve
    let addr = "0.0.0.0:4000";
    let listener = TcpListener::bind(addr).await?;
    tracing::info!("Listening on {}", addr);

    axum::serve(listener, app).await?;

    Ok(())
}
