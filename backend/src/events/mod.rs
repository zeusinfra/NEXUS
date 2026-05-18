use serde::{Deserialize, Serialize};
use tokio::sync::broadcast;
use std::sync::Arc;

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
    AgentStarted { agent_id: String },
    AgentStopped { agent_id: String },
    MessageReceived { message: String },
    MessageStreamChunk { id: String, chunk: String },
    MemoryUpdated { key: String },
    SystemStateChanged { metrics: serde_json::Value },
    FileChanged { path: String },
    
    // Action / Execution Lifecycle
    ApprovalRequested { command_id: String, command: String, risk: RiskLevel },
    ApprovalAccepted { command_id: String },
    ApprovalDenied { command_id: String },
    ActionBlocked { reason: String },
    CommandStarted { command_id: String, command: String },
    CommandOutput { command_id: String, chunk: String, is_error: bool },
    CommandFinished { command_id: String, exit_code: i32 },
    CommandFailed { command_id: String, error: String },
    PatchPreview { path: String, diff: String },
    RollbackCreated { backup_path: String },
    FilePatched { path: String },
    TaskCreated { task_id: String, description: String },
    TaskCompleted { task_id: String },
    TaskFailed { task_id: String, error: String },
    TaskStateChanged { task_id: String, state: String, message: String },
    EvidenceGenerated { task_id: String, evidence_type: String, content: Option<String>, diff: Option<String>, backup_path: Option<String> },
}

#[derive(Clone)]
pub struct EventBus {
    tx: broadcast::Sender<SystemEvent>,
}

impl EventBus {
    pub fn new(capacity: usize) -> Self {
        let (tx, _) = broadcast::channel(capacity);
        Self { tx }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<SystemEvent> {
        self.tx.subscribe()
    }

    pub fn publish(&self, event: SystemEvent) -> Result<usize, broadcast::error::SendError<SystemEvent>> {
        self.tx.send(event)
    }
}
