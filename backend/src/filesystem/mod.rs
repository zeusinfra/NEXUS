use crate::{events::SystemEvent, state::AppState};
use notify::{Config, Event, RecommendedWatcher, RecursiveMode, Watcher};
use std::path::Path;
use std::sync::Arc;
use tokio::sync::mpsc;

pub fn start_watcher(state: Arc<AppState>, watch_path: &str) {
    let path_to_watch = watch_path.to_string();

    tokio::spawn(async move {
        let (tx, mut rx) = mpsc::channel(100);

        let mut watcher = RecommendedWatcher::new(
            move |res: Result<Event, notify::Error>| {
                if let Ok(event) = res {
                    let _ = tx.blocking_send(event);
                }
            },
            Config::default(),
        )
        .expect("Failed to initialize filesystem watcher");

        watcher
            .watch(Path::new(&path_to_watch), RecursiveMode::Recursive)
            .expect("Failed to watch directory");

        tracing::info!("Filesystem watcher started on: {}", path_to_watch);

        // Process events in the async context and bridge to EventBus
        while let Some(event) = rx.recv().await {
            match event.kind {
                notify::EventKind::Modify(_)
                | notify::EventKind::Create(_)
                | notify::EventKind::Remove(_) => {
                    for path in event.paths {
                        if let Some(path_str) = path.to_str() {
                            // Don't broadcast sqlite journal modifications to avoid infinite loops/spam
                            if path_str.contains(".db-wal")
                                || path_str.contains(".db-shm")
                                || path_str.contains("nexus_backend.db")
                            {
                                continue;
                            }

                            let _ = state.event_bus.publish(SystemEvent::FileChanged {
                                path: path_str.to_string(),
                            });
                        }
                    }
                }
                _ => {}
            }
        }
    });
}
