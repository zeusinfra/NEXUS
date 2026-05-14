use axum::{
    extract::ws::{Message, WebSocket, WebSocketUpgrade},
    response::IntoResponse,
    routing::get,
    Router,
};
use notify::{Config, RecursiveMode, Watcher};
use serde::{Deserialize, Serialize};
use std::{env, path::Path, sync::Arc, time::Duration};
use sysinfo::System;
use tokio::sync::broadcast;
use tower_http::cors::CorsLayer;

#[derive(Serialize, Deserialize, Debug, Clone)]
#[serde(tag = "type")]
enum NexusEvent {
    #[serde(rename = "file_event")]
    File {
        event_kind: String,
        path: String,
        project: String,
    },
    #[serde(rename = "telemetry")]
    Telemetry {
        cpu_usage: f32,
        ram_usage: f32,
        disk_usage: f32,
    },
}

struct AppState {
    tx: broadcast::Sender<NexusEvent>,
}

#[tokio::main]
async fn main() {
    dotenv::dotenv().ok();

    // Configurações
    let port = std::env::var("NEXUS_WATCHER_PORT").unwrap_or_else(|_| "8081".to_string());
    let (tx, _rx) = broadcast::channel(100);
    let app_state = Arc::new(AppState { tx: tx.clone() });

    // Loop de Telemetria (Background)
    let tx_telemetry = tx.clone();
    tokio::spawn(async move {
        let mut sys = System::new_all();
        loop {
            sys.refresh_cpu();
            sys.refresh_memory();

            let event = NexusEvent::Telemetry {
                cpu_usage: sys.global_cpu_info().cpu_usage(),
                ram_usage: (sys.used_memory() as f32 / sys.total_memory() as f32) * 100.0,
                disk_usage: 0.0, // Simplificado
            };

            let _ = tx_telemetry.send(event);
            tokio::time::sleep(Duration::from_secs(2)).await;
        }
    });

    // Watcher de Arquivos (Background)
    let tx_files = tx.clone();
    tokio::spawn(async move {
        let (watcher_tx, mut watcher_rx) = tokio::sync::mpsc::channel(100);

        let mut watcher = notify::RecommendedWatcher::new(
            move |res| {
                let _ = watcher_tx.blocking_send(res);
            },
            Config::default(),
        )
        .expect("Error creating watcher");

        let home = env::var("HOME").unwrap_or_else(|_| "/home/nexus".to_string());
        let watch_dirs: Vec<String> = env::var("NEXUS_WATCH_DIRS")
            .ok()
            .map(|raw| {
                raw.split(',')
                    .map(str::trim)
                    .filter(|item| !item.is_empty())
                    .map(|item| item.replace("$HOME", &home))
                    .collect()
            })
            .unwrap_or_else(|| {
                vec![
                    format!("{}/Documentos/NEXUS/NEXUS", home),
                    format!("{}/Documentos/Brain", home),
                ]
            });

        for dir in watch_dirs {
            if Path::new(&dir).exists() {
                let _ = watcher.watch(Path::new(&dir), RecursiveMode::Recursive);
            }
        }

        while let Some(res) = watcher_rx.recv().await {
            if let Ok(event) = res {
                for path in event.paths {
                    if !is_ignored(&path) {
                        let ev = NexusEvent::File {
                            event_kind: format!("{:?}", event.kind),
                            path: path.to_string_lossy().into_owned(),
                            project: get_project(&path),
                        };
                        // Mantém compatibilidade com o pipe do Python
                        println!("{}", serde_json::to_string(&ev).unwrap());
                        let _ = tx_files.send(ev);
                    }
                }
            }
        }
    });

    // Servidor WebSocket (Axum)
    let app = Router::new()
        .route("/ws", get(ws_handler))
        .layer(CorsLayer::permissive())
        .with_state(app_state);

    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", port))
        .await
        .unwrap();
    println!("🧠 NEXUS Watcher Hub rodando em ws://0.0.0.0:{}/ws", port);
    axum::serve(listener, app).await.unwrap();
}

async fn ws_handler(
    ws: WebSocketUpgrade,
    state: axum::extract::State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(|socket| handle_socket(socket, state))
}

async fn handle_socket(mut socket: WebSocket, state: axum::extract::State<Arc<AppState>>) {
    let mut rx = state.tx.subscribe();

    while let Ok(event) = rx.recv().await {
        let msg = serde_json::to_string(&event).unwrap();
        if socket.send(Message::Text(msg)).await.is_err() {
            break;
        }
    }
}

fn get_project(path: &Path) -> String {
    let path_str = path.to_string_lossy();
    if path_str.contains("NEXUS_BRAIN") {
        "NEXUS_BRAIN".to_string()
    } else if path_str.contains("ZEUS_SYSTEM") {
        "ZEUS_SYSTEM".to_string()
    } else {
        "unknown".to_string()
    }
}

fn is_ignored(path: &Path) -> bool {
    let ignored = [
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "target",
        "dist",
        "build",
        "logs",
        "data",
        "scratch",
        ".obsidian",
        ".pytest_cache",
        ".ruff_cache",
    ];
    for part in path.components() {
        let p = part.as_os_str().to_string_lossy();
        if p.starts_with('.') || ignored.contains(&p.as_ref()) {
            return true;
        }
    }
    let Some(name) = path.file_name().and_then(|value| value.to_str()) else {
        return false;
    };
    let runtime_files = [
        "nexus_events.db",
        "nexus_events.db-journal",
        "nexus_events.db-wal",
        "nexus_events.db-shm",
        "nexus_core.log",
        "nexus_server.log",
    ];
    if runtime_files.contains(&name) {
        return true;
    }
    let lowered = name.to_ascii_lowercase();
    let runtime_suffixes = [
        ".db",
        ".sqlite",
        ".sqlite3",
        ".db-journal",
        ".db-wal",
        ".db-shm",
        ".log",
        ".tmp",
        ".pyc",
        ".lock",
        ".pid",
        ".onnx",
        ".mp3",
    ];
    if runtime_suffixes
        .iter()
        .any(|suffix| lowered.ends_with(suffix))
    {
        return true;
    }
    false
}

#[cfg(test)]
mod tests {
    use super::{get_project, is_ignored};
    use std::path::Path;

    #[test]
    fn get_project_classifies_known_roots() {
        assert_eq!(
            get_project(Path::new("/home/zeus/Documentos/NEXUS_BRAIN/a.md")),
            "NEXUS_BRAIN"
        );
        assert_eq!(
            get_project(Path::new("/home/zeus/Documentos/ZEUS_SYSTEM/a.md")),
            "ZEUS_SYSTEM"
        );
        assert_eq!(get_project(Path::new("/tmp/a.md")), "unknown");
    }

    #[test]
    fn is_ignored_blocks_runtime_and_hidden_paths() {
        assert!(is_ignored(Path::new("/repo/.git/config")));
        assert!(is_ignored(Path::new("/repo/logs/app.log")));
        assert!(is_ignored(Path::new("/repo/data/nexus_memory.db")));
        assert!(is_ignored(Path::new("/repo/nexus_events.db-journal")));
        assert!(is_ignored(Path::new("/repo/nexus_core.log")));
        assert!(is_ignored(Path::new("/repo/target/debug/app")));
        assert!(!is_ignored(Path::new("/repo/apps/web_gui.py")));
    }
}
