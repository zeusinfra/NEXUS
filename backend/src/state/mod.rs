use dashmap::DashMap;
use std::sync::Arc;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentState {
    pub id: String,
    pub status: String,
}

#[derive(Clone)]
pub struct AppState {
    pub active_agents: Arc<DashMap<String, AgentState>>,
    pub system_metrics: Arc<DashMap<String, String>>,
    pub event_bus: crate::events::EventBus,
    pub db: Arc<crate::storage::Database>,
    pub approvals: Arc<crate::approvals::ApprovalEngine>,
    pub executor: Arc<crate::execution::command::CommandExecutor>,
    pub task_graph: Arc<crate::execution::graph::TaskGraphEngine>,
    pub patcher: Arc<crate::execution::patch::FilePatchEngine>,
    pub test_runner: Arc<crate::execution::test::TestRunner>,
}

impl AppState {
    pub fn new(
        event_bus: crate::events::EventBus,
        db: Arc<crate::storage::Database>,
        approvals: Arc<crate::approvals::ApprovalEngine>,
        executor: Arc<crate::execution::command::CommandExecutor>,
        task_graph: Arc<crate::execution::graph::TaskGraphEngine>,
        patcher: Arc<crate::execution::patch::FilePatchEngine>,
        test_runner: Arc<crate::execution::test::TestRunner>,
    ) -> Self {
        Self {
            active_agents: Arc::new(DashMap::new()),
            system_metrics: Arc::new(DashMap::new()),
            event_bus,
            db,
            approvals,
            executor,
            task_graph,
            patcher,
            test_runner,
        }
    }
}
