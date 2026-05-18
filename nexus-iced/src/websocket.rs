use futures_util::{SinkExt, StreamExt};
use iced::subscription::{self, Subscription};
use serde::{Deserialize, Serialize};
use tokio_tungstenite::connect_async;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum RiskLevel {
    Safe,
    Moderate,
    Dangerous,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum SystemEvent {
    AgentStarted {
        agent_id: String,
    },
    AgentStopped {
        agent_id: String,
    },
    MessageReceived {
        message: String,
    },
    MessageStreamChunk {
        id: String,
        chunk: String,
    },
    MemoryUpdated {
        key: String,
    },
    SystemStateChanged {
        metrics: serde_json::Value,
    },
    FileChanged {
        path: String,
    },

    ApprovalRequested {
        command_id: String,
        command: String,
        risk: RiskLevel,
    },
    ApprovalAccepted {
        command_id: String,
    },
    ApprovalDenied {
        command_id: String,
    },
    ActionBlocked {
        reason: String,
    },
    CommandStarted {
        command_id: String,
        command: String,
    },
    CommandOutput {
        command_id: String,
        chunk: String,
        is_error: bool,
    },
    CommandFinished {
        command_id: String,
        exit_code: i32,
    },
    CommandFailed {
        command_id: String,
        error: String,
    },
    PatchPreview {
        path: String,
        diff: String,
    },
    RollbackCreated {
        backup_path: String,
    },
    FilePatched {
        path: String,
    },
    TaskCreated {
        task_id: String,
        description: String,
    },
    TaskCompleted {
        task_id: String,
    },
    TaskFailed {
        task_id: String,
        error: String,
    },
    TaskStateChanged {
        task_id: String,
        state: String,
        message: String,
    },
    EvidenceGenerated {
        task_id: String,
        evidence_type: String,
        content: Option<String>,
        diff: Option<String>,
        backup_path: Option<String>,
    },
}

#[derive(Debug, Clone)]
pub enum Event {
    Connected,
    Disconnected,
    MessageReceived(SystemEvent),
    Error(String),
}

pub fn connect() -> Subscription<Event> {
    subscription::channel(
        std::any::TypeId::of::<SystemEvent>(),
        100,
        |mut output| async move {
            let url = "ws://127.0.0.1:4000/ws";

            loop {
                match connect_async(url).await {
                    Ok((mut ws_stream, _)) => {
                        let _ = output.send(Event::Connected).await;

                        while let Some(msg) = ws_stream.next().await {
                            match msg {
                                Ok(tokio_tungstenite::tungstenite::Message::Text(text)) => {
                                    if let Ok(event) = serde_json::from_str::<SystemEvent>(&text) {
                                        let _ = output.send(Event::MessageReceived(event)).await;
                                    }
                                }
                                Ok(tokio_tungstenite::tungstenite::Message::Close(_)) => {
                                    break;
                                }
                                Err(_) => {
                                    break;
                                }
                                _ => {}
                            }
                        }

                        let _ = output.send(Event::Disconnected).await;
                    }
                    Err(e) => {
                        let _ = output.send(Event::Error(e.to_string())).await;
                    }
                }

                // Wait before reconnecting
                tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
            }
        },
    )
}
