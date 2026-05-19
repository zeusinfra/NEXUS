use crate::{events::SystemEvent, state::AppState};
use std::sync::Arc;
use std::time::Duration;
use tokio::time::sleep;

pub fn start_background_workers(state: Arc<AppState>) {
    let state_clone = Arc::clone(&state);
    tokio::spawn(async move {
        // Simulate background metrics streaming
        let mut count = 0;
        loop {
            sleep(Duration::from_secs(5)).await;
            count += 1;
            let _ = state_clone
                .event_bus
                .publish(SystemEvent::SystemStateChanged {
                    metrics: serde_json::json!({
                        "cpu_usage": "1.2%",
                        "ram_usage": "45MB",
                        "tick": count,
                    }),
                });
        }
    });
}
