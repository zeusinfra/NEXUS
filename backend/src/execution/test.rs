use crate::events::{EventBus, SystemEvent};
use std::process::Stdio;
use tokio::process::Command;

#[derive(Clone)]
pub struct TestRunner {
    event_bus: EventBus,
}

impl TestRunner {
    pub fn new(event_bus: EventBus) -> Self {
        Self { event_bus }
    }

    pub async fn run_tests(
        &self,
        task_id: &str,
        test_command: &str,
    ) -> Result<(i32, String), String> {
        let _ = self.event_bus.publish(SystemEvent::TaskStateChanged {
            task_id: task_id.to_string(),
            state: "testing".to_string(),
            message: test_command.to_string(),
        });

        let child = Command::new("bash")
            .arg("-c")
            .arg(test_command)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| e.to_string())?;

        let output = child.wait_with_output().await.map_err(|e| e.to_string())?;

        let exit_code = output.status.code().unwrap_or(-1);
        let stdout_str = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr_str = String::from_utf8_lossy(&output.stderr).to_string();

        let mut combined = stdout_str;
        combined.push('\n');
        combined.push_str(&stderr_str);

        let _ = self.event_bus.publish(SystemEvent::EvidenceGenerated {
            task_id: task_id.to_string(),
            evidence_type: "test_output".to_string(),
            content: Some(combined.clone()),
            diff: None,
            backup_path: None,
        });

        Ok((exit_code, combined))
    }
}
