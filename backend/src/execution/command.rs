use crate::events::{EventBus, SystemEvent};
use std::process::Stdio;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

#[derive(Clone)]
pub struct CommandExecutor {
    event_bus: EventBus,
}

impl CommandExecutor {
    pub fn new(event_bus: EventBus) -> Self {
        Self { event_bus }
    }

    pub async fn execute(
        &self,
        command_id: &str,
        cmd_string: &str,
    ) -> Result<(i32, String), String> {
        let event_bus_clone = self.event_bus.clone();
        let c_id = command_id.to_string();

        let _ = event_bus_clone.publish(SystemEvent::CommandStarted {
            command_id: c_id.clone(),
            command: cmd_string.to_string(),
        });

        let mut child = Command::new("bash")
            .arg("-c")
            .arg(cmd_string)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| e.to_string())?;

        let stdout = child.stdout.take().expect("Failed to open stdout");
        let stderr = child.stderr.take().expect("Failed to open stderr");

        let event_bus_out = self.event_bus.clone();
        let cid_out = c_id.clone();
        let out_handle = tokio::spawn(async move {
            let mut reader = BufReader::new(stdout).lines();
            let mut acc = String::new();
            while let Ok(Some(line)) = reader.next_line().await {
                let chunk = format!("{}\n", line);
                acc.push_str(&chunk);
                let _ = event_bus_out.publish(SystemEvent::CommandOutput {
                    command_id: cid_out.clone(),
                    chunk,
                    is_error: false,
                });
            }
            acc
        });

        let event_bus_err = self.event_bus.clone();
        let cid_err = c_id.clone();
        let err_handle = tokio::spawn(async move {
            let mut reader = BufReader::new(stderr).lines();
            let mut acc = String::new();
            while let Ok(Some(line)) = reader.next_line().await {
                let chunk = format!("{}\n", line);
                acc.push_str(&chunk);
                let _ = event_bus_err.publish(SystemEvent::CommandOutput {
                    command_id: cid_err.clone(),
                    chunk,
                    is_error: true,
                });
            }
            acc
        });

        let status = child.wait().await.map_err(|e| e.to_string())?;

        // Wait for streams to finish
        let (out_result, err_result) = tokio::join!(out_handle, err_handle);

        let exit_code = status.code().unwrap_or(-1);

        let _ = event_bus_clone.publish(SystemEvent::CommandFinished {
            command_id: c_id,
            exit_code,
        });

        let mut final_out = String::new();
        if let Ok(o) = out_result {
            final_out.push_str(&o);
        }
        if let Ok(e) = err_result {
            final_out.push_str(&e);
        }

        Ok((exit_code, final_out))
    }
}
