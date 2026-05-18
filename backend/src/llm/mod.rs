use crate::{events::{SystemEvent, RiskLevel}, state::AppState, execution::risk::RiskClassifier, execution::graph::TaskStatus};
use async_stream::stream;
use futures::Stream;
use std::sync::Arc;
use tokio::time::{sleep, Duration};
use uuid::Uuid;

pub struct LlmRouter {
    state: Arc<AppState>,
}

impl LlmRouter {
    pub fn new(state: Arc<AppState>) -> Self {
        Self { state }
    }

    pub fn process_prompt(&self, prompt: &str) -> impl Stream<Item = String> {
        let prompt_clone = prompt.to_string();
        let state = Arc::clone(&self.state);

        stream! {
            let request_id = Uuid::new_v4().to_string();

            // === COMMAND MODE: prefixed with '/' ===
            if prompt_clone.starts_with("/") {
                let command = prompt_clone.strip_prefix("/").unwrap().trim().to_string();
                let risk = RiskClassifier::classify(&command);

                // 1. Create Task in the TaskGraph
                let task_id = match state.task_graph.create_task(&format!("Executar: {}", command), None).await {
                    Ok(id) => id,
                    Err(e) => {
                        yield format!("Erro ao criar tarefa: {}", e);
                        return;
                    }
                };

                // 2. Transition to Running
                let _ = state.task_graph.transition_task(&task_id, TaskStatus::Running).await;

                let preamble = format!("⚡ Risco: {:?} │ Task: {}\n", risk, &task_id[..8]);
                for c in preamble.chars() {
                    yield c.to_string();
                    sleep(Duration::from_millis(15)).await;
                }

                // 3. Approval gate for dangerous commands
                if risk == RiskLevel::Dangerous || risk == RiskLevel::Critical {
                    state.approvals.request_approval(&request_id, &command, risk);
                    yield "\n⛔ Comando perigoso — aprovação solicitada na GUI.\n".to_string();
                    // Evidence: we record the approval request itself
                    let _ = state.task_graph.record_evidence(
                        &task_id, "approval_requested", Some(&command), None, None, None, "pending",
                    ).await;
                    return;
                }

                // 4. Execute safe/moderate commands immediately
                yield "✅ Seguro. Executando...\n".to_string();
                let result = state.executor.execute(&request_id, &command).await;

                match result {
                    Ok((exit_code, stdout)) => {
                        // 5. Record execution evidence
                        let status_str = if exit_code == 0 { "success" } else { "failed" };
                        let _ = state.task_graph.record_evidence(
                            &task_id, "command", Some(&command), Some(&stdout), None, None, status_str,
                        ).await;

                        // 6. Emit evidence event to GUI
                        let _ = state.event_bus.publish(SystemEvent::EvidenceGenerated {
                            task_id: task_id.clone(),
                            evidence_type: "command".to_string(),
                            content: Some(stdout.clone()),
                            diff: None,
                            backup_path: None,
                        });

                        // 7. Auto-run tests if applicable
                        let _ = state.task_graph.transition_task(&task_id, TaskStatus::Testing).await;
                        let test_result = state.test_runner.run_tests(&task_id, "cargo check 2>&1").await;
                        match test_result {
                            Ok((test_exit, test_out)) => {
                                let test_status = if test_exit == 0 { "success" } else { "failed" };
                                let _ = state.task_graph.record_evidence(
                                    &task_id, "test", Some("cargo check"), Some(&test_out), None, None, test_status,
                                ).await;
                                let _ = state.event_bus.publish(SystemEvent::EvidenceGenerated {
                                    task_id: task_id.clone(),
                                    evidence_type: "test".to_string(),
                                    content: Some(test_out),
                                    diff: None,
                                    backup_path: None,
                                });
                            }
                            Err(e) => {
                                let _ = state.task_graph.record_evidence(
                                    &task_id, "test", Some("cargo check"), Some(&e), None, None, "failed",
                                ).await;
                            }
                        }

                        // 8. Transition to Done (will succeed because evidence was recorded)
                        let final_status = if exit_code == 0 { TaskStatus::Done } else { TaskStatus::Failed };
                        let _ = state.task_graph.transition_task(&task_id, final_status).await;

                        // 9. Summary with proof
                        let summary = format!(
                            "\n━━━━━━━━━━━━━━━━━━━━\n📋 Resumo da Tarefa {}\n🔹 Comando: {}\n🔹 Exit code: {}\n🔹 Status: {}\n━━━━━━━━━━━━━━━━━━━━\n",
                            &task_id[..8], command, exit_code, status_str
                        );
                        yield summary;
                    }
                    Err(e) => {
                        let _ = state.task_graph.record_evidence(
                            &task_id, "command", Some(&command), Some(&e), None, None, "failed",
                        ).await;
                        let _ = state.task_graph.transition_task(&task_id, TaskStatus::Failed).await;
                        yield format!("\n❌ Falha na execução: {}\n", e);
                    }
                }

                return;
            }

            // === CONVERSATIONAL MODE ===
            let mock_response = format!(
                "Analisando sua solicitação: '{}'.\n\nIdentifiquei 3 fatores principais. Inicializando módulos reativos.\n\nProcesso finalizado.",
                prompt_clone
            );

            for chunk in mock_response.chars() {
                yield chunk.to_string();
                sleep(Duration::from_millis(15)).await;
            }
        }
    }
}
