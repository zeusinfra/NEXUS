use crate::events::EventBus;
use tokio::process::Command;
use std::process::Stdio;

#[derive(Clone)]
pub struct TestRunner {
    event_bus: EventBus,
}

impl TestRunner {
    pub fn new(event_bus: EventBus) -> Self {
        Self { event_bus }
    }

    pub async fn run_tests(&self, task_id: &str, test_command: &str) -> Result<(i32, String), String> {
        let mut child = Command::new("bash")
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
        combined.push_str("\n");
        combined.push_str(&stderr_str);

        Ok((exit_code, combined))
    }
}
