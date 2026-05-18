use crate::events::{SystemEvent, RiskLevel, EventBus};
use std::sync::Arc;
use dashmap::DashMap;

#[derive(Clone)]
pub struct ApprovalEngine {
    event_bus: EventBus,
    pending_approvals: Arc<DashMap<String, String>>, // command_id -> command
}

impl ApprovalEngine {
    pub fn new(event_bus: EventBus) -> Self {
        Self {
            event_bus,
            pending_approvals: Arc::new(DashMap::new()),
        }
    }

    pub fn request_approval(&self, command_id: &str, command: &str, risk: RiskLevel) {
        self.pending_approvals.insert(command_id.to_string(), command.to_string());
        
        let _ = self.event_bus.publish(SystemEvent::ApprovalRequested {
            command_id: command_id.to_string(),
            command: command.to_string(),
            risk,
        });
    }

    pub fn approve(&self, command_id: &str) -> Option<String> {
        if let Some((_, command)) = self.pending_approvals.remove(command_id) {
            let _ = self.event_bus.publish(SystemEvent::ApprovalAccepted {
                command_id: command_id.to_string(),
            });
            Some(command)
        } else {
            None
        }
    }

    pub fn deny(&self, command_id: &str) {
        if self.pending_approvals.remove(command_id).is_some() {
            let _ = self.event_bus.publish(SystemEvent::ApprovalDenied {
                command_id: command_id.to_string(),
            });
        }
    }
}
