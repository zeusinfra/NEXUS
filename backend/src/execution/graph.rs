use crate::{events::{SystemEvent, EventBus}, storage::Database};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Clone)]
pub struct TaskGraphEngine {
    event_bus: EventBus,
    db: Arc<Database>,
}

pub enum TaskStatus {
    Planning,
    Running,
    Testing,
    Done,
    Failed,
}

impl TaskStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            TaskStatus::Planning => "planning",
            TaskStatus::Running => "running",
            TaskStatus::Testing => "testing",
            TaskStatus::Done => "done",
            TaskStatus::Failed => "failed",
        }
    }
}

impl TaskGraphEngine {
    pub fn new(event_bus: EventBus, db: Arc<Database>) -> Self {
        Self { event_bus, db }
    }

    pub async fn create_task(&self, objective: &str, parent_id: Option<&str>) -> Result<String, sqlx::Error> {
        let task_id = Uuid::new_v4().to_string();
        let status = TaskStatus::Planning.as_str();

        sqlx::query("INSERT INTO task_graph (id, parent_id, objective, status) VALUES (?, ?, ?, ?)")
            .bind(&task_id)
            .bind(parent_id)
            .bind(objective)
            .bind(status)
            .execute(&self.db.pool)
            .await?;

        let _ = self.event_bus.publish(SystemEvent::TaskCreated {
            task_id: task_id.clone(),
            description: objective.to_string(),
        });

        Ok(task_id)
    }

    pub async fn transition_task(&self, task_id: &str, new_status: TaskStatus) -> Result<(), String> {
        // Enforce evidence check if transitioning to Done
        if let TaskStatus::Done = new_status {
            let row: Option<(i64,)> = sqlx::query_as("SELECT COUNT(*) FROM execution_history WHERE task_id = ?")
                .bind(task_id)
                .fetch_optional(&self.db.pool)
                .await
                .map_err(|e| e.to_string())?;

            if row.is_none() || row.unwrap().0 == 0 {
                return Err("Cannot mark task as Done without execution evidence".to_string());
            }
        }

        sqlx::query("UPDATE task_graph SET status = ? WHERE id = ?")
            .bind(new_status.as_str())
            .bind(task_id)
            .execute(&self.db.pool)
            .await
            .map_err(|e| e.to_string())?;

        let event = match new_status {
            TaskStatus::Done => SystemEvent::TaskCompleted { task_id: task_id.to_string() },
            TaskStatus::Failed => SystemEvent::TaskFailed { task_id: task_id.to_string(), error: "Failed".to_string() },
            _ => return Ok(()),
        };

        let _ = self.event_bus.publish(event);

        Ok(())
    }

    pub async fn record_evidence(&self, task_id: &str, action_type: &str, command: Option<&str>, stdout: Option<&str>, diff: Option<&str>, evidence_path: Option<&str>, status: &str) -> Result<(), sqlx::Error> {
        let ev_id = Uuid::new_v4().to_string();
        sqlx::query("INSERT INTO execution_history (id, task_id, action_type, command, stdout, diff, evidence_path, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
            .bind(ev_id)
            .bind(task_id)
            .bind(action_type)
            .bind(command)
            .bind(stdout)
            .bind(diff)
            .bind(evidence_path)
            .bind(status)
            .execute(&self.db.pool)
            .await?;
        
        Ok(())
    }
}
