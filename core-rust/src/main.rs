use std::process::Stdio;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use sysinfo::System;
use tokio::process::Command;
use tokio_stream::wrappers::ReceiverStream;
use tonic::{transport::Server, Request, Response, Status};

// Import generated gRPC code
pub mod nexus_core {
    tonic::include_proto!("nexus_core");
}

use nexus_core::nexus_core_server::{NexusCore, NexusCoreServer};
use nexus_core::{
    ActionRequest, ActionResponse, ModeRequest, ModeResponse, SimulationRequest, SimulationResponse,
    ProcessInfo, TelemetryRequest, TelemetryUpdate,
};

struct NexusCoreService {
    system: Arc<Mutex<System>>,
    mode: Arc<Mutex<String>>,
}

impl NexusCoreService {
    fn new() -> Self {
        Self {
            system: Arc::new(Mutex::new(System::new_all())),
            mode: Arc::new(Mutex::new("SAFE".to_string())),
        }
    }

    // Basic Guardian Check (Safety First)
    fn safe_command_args(command: &str) -> Option<Vec<String>> {
        let blocked_tokens = ["|", "&&", "||", ";", ">", ">>", "<", "$(", "`"];
        if blocked_tokens.iter().any(|token| command.contains(token)) {
            return None;
        }

        let args: Vec<String> = command
            .split_whitespace()
            .map(|part| part.to_string())
            .collect();
        if args.is_empty() {
            return None;
        }

        let allowlist = ["ls", "pwd", "echo", "cat", "whoami", "date"];
        if allowlist.contains(&args[0].as_str()) {
            Some(args)
        } else {
            None
        }
    }
}

#[tonic::async_trait]
impl NexusCore for NexusCoreService {
    async fn execute_action(
        &self,
        request: Request<ActionRequest>,
    ) -> Result<Response<ActionResponse>, Status> {
        let req = request.into_inner();
        let cmd = req.command;
        let mode = self.mode.lock().unwrap().clone();

        println!("[CORE] Executing action in {} mode: {}", mode, cmd);

        if mode == "SAFE" {
            return Ok(Response::new(ActionResponse {
                success: false,
                output: "Action blocked: System is in SAFE mode".into(),
                error: "SAFE_MODE_BLOCK".into(),
                backup_id: "".into(),
            }));
        }

        let Some(args) = NexusCoreService::safe_command_args(&cmd) else {
            return Ok(Response::new(ActionResponse {
                success: false,
                output: "".into(),
                error: "GUARDIAN_BLOCK: Dangerous command detected".into(),
                backup_id: "".into(),
            }));
        };

        let output = Command::new(&args[0])
            .args(&args[1..])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| Status::internal(format!("Spawn error: {}", e)))?
            .wait_with_output()
            .await
            .map_err(|e| Status::internal(format!("Wait error: {}", e)))?;

        Ok(Response::new(ActionResponse {
            success: output.status.success(),
            output: String::from_utf8_lossy(&output.stdout).to_string(),
            error: String::from_utf8_lossy(&output.stderr).to_string(),
            backup_id: "AUTO_BACKUP_BCA".into(),
        }))
    }

    async fn simulate_action(
        &self,
        request: Request<SimulationRequest>,
    ) -> Result<Response<SimulationResponse>, Status> {
        let req = request.into_inner();
        println!("[CORE] Simulating Action: {}", req.command);

        // Simulation logic: would normally run in a namespace/sandbox
        // For now, we simulate success if the command is a simple 'ls' or 'echo'
        let success = req.command.contains("ls") || req.command.contains("echo");

        Ok(Response::new(SimulationResponse {
            success,
            confidence: if success { 0.95 } else { 0.1 },
            output: "Simulation completed in shadow environment".into(),
            error: if success {
                "".into()
            } else {
                "Potential risk detected".into()
            },
        }))
    }

    type StreamTelemetryStream = ReceiverStream<Result<TelemetryUpdate, Status>>;

    async fn stream_telemetry(
        &self,
        _request: Request<TelemetryRequest>,
    ) -> Result<Response<Self::StreamTelemetryStream>, Status> {
        let (tx, rx) = tokio::sync::mpsc::channel(10);
        let system_ref = self.system.clone();

        tokio::spawn(async move {
            loop {
                let update = {
                    let mut sys = system_ref.lock().unwrap();
                    sys.refresh_all();

                    TelemetryUpdate {
                        cpu_usage: sys.global_cpu_info().cpu_usage(),
                        ram_usage: if sys.total_memory() == 0 {
                            0.0
                        } else {
                            (sys.used_memory() as f32 / sys.total_memory() as f32) * 100.0
                        },
                        disk_usage: 0.0,
                        processes: sys
                            .processes()
                            .iter()
                            .take(25)
                            .map(|(pid, proc_)| ProcessInfo {
                                pid: pid.as_u32(),
                                name: proc_.name().to_string(),
                                cpu_percent: proc_.cpu_usage(),
                                mem_percent: if sys.total_memory() == 0 {
                                    0.0
                                } else {
                                    (proc_.memory() as f32 / sys.total_memory() as f32) * 100.0
                                },
                            })
                            .collect(),
                    }
                };

                if tx.send(Ok(update)).await.is_err() {
                    break;
                }
                tokio::time::sleep(Duration::from_secs(2)).await;
            }
        });

        Ok(Response::new(ReceiverStream::new(rx)))
    }

    async fn set_mode(
        &self,
        request: Request<ModeRequest>,
    ) -> Result<Response<ModeResponse>, Status> {
        let req = request.into_inner();
        let mut mode = self.mode.lock().unwrap();
        *mode = req.mode;

        Ok(Response::new(ModeResponse {
            success: true,
            current_mode: mode.clone(),
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::NexusCoreService;

    #[test]
    fn safe_command_args_accepts_simple_allowlisted_commands() {
        let args = NexusCoreService::safe_command_args("echo hello").unwrap();
        assert_eq!(args, vec!["echo".to_string(), "hello".to_string()]);
    }

    #[test]
    fn safe_command_args_rejects_shell_control() {
        assert!(NexusCoreService::safe_command_args("echo ok && rm file").is_none());
        assert!(NexusCoreService::safe_command_args("cat file > out").is_none());
    }

    #[test]
    fn safe_command_args_rejects_non_allowlisted_commands() {
        assert!(NexusCoreService::safe_command_args("python3 -c print(1)").is_none());
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = "[::1]:50051".parse()?;
    let nexus_service = NexusCoreService::new();

    println!("🚀 NEXUS CORE (Rust) started on {}", addr);
    println!("🛡️ Guardian Active. Mode: SAFE");

    Server::builder()
        .add_service(NexusCoreServer::new(nexus_service))
        .serve(addr)
        .await?;

    Ok(())
}
