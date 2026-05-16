use iced::widget::{button, container, scrollable, text, text_input, Column, Row, Rule, Space};
use iced::{
    Alignment, Application, Border, Color, Command, Element, Length, Settings, Subscription, Theme,
};
use reqwest::Client;
use rodio::{Decoder, OutputStream, Sink};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use std::io::Cursor;
use std::path::PathBuf;
use std::time::{Duration, Instant};
use sysinfo::System;
use tokio::process::Command as TokioCommand;

pub fn main() -> iced::Result {
    NexusApp::run(Settings {
        window: iced::window::Settings {
            size: iced::Size::new(1100.0, 820.0),
            ..Default::default()
        },
        ..Default::default()
    })
}

struct NexusApp {
    input_value: String,
    messages: Vec<ChatMessage>,
    status: String,
    client: Client,
    system: System,
    cpu_usage: f32,
    ram_usage: f32,
    is_thinking: bool,
    is_playing_audio: bool,
    session_start: Instant,
    last_latency_ms: Option<u64>,
    tick_counter: u32,
    pending_since: Option<Instant>,
    current_stage: String,
    activity: Vec<ActivityItem>,
    org: OrgDashboard,
    selected_pending_proposal: Option<String>,
    selected_approved_proposal: Option<String>,
    org_action_in_flight: bool,
}

#[derive(Clone, Debug)]
struct ChatMessage {
    role: String,
    content: String,
    timestamp: String,
}

#[derive(Clone, Debug)]
struct ActivityItem {
    label: String,
    detail: String,
    timestamp: String,
    level: ActivityLevel,
}

#[derive(Clone, Debug)]
enum ActivityLevel {
    Info,
    Success,
    Warning,
    Error,
}

#[derive(Clone, Debug, Default)]
struct OrgDashboard {
    health: Option<OrgHealth>,
    memory: Option<OrgMemoryStatus>,
    agent_ticks: Vec<AgentTick>,
    approvals: Vec<ApprovalItem>,
    approved_commands: Vec<ApprovalItem>,
    runtime_events: Vec<RuntimeEvent>,
    verifications: Vec<VerificationItem>,
    org_events: Vec<OrgEvent>,
    swarm: Option<SwarmStatus>,
    incidents: Vec<IncidentItem>,
    updated_at: Option<String>,
    error: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
struct OrgHealth {
    status: String,
    mode: String,
    #[serde(alias = "agents")]
    agents_registered: usize,
    #[serde(alias = "tasks")]
    tasks_total: usize,
    detail: String,
    #[serde(alias = "heartbeat_age_s")]
    heartbeat_age_seconds: Option<f64>,
}

#[derive(Clone, Debug, Deserialize)]
struct OrgMemoryStatus {
    decisions: i64,
    tasks: i64,
    events: i64,
    summaries: i64,
    runtime_events: i64,
    verifications: i64,
    observations: i64,
    agent_ticks: i64,
}

#[derive(Clone, Debug, Deserialize)]
struct AgentTick {
    #[serde(alias = "agent_role")]
    agent_id: String,
    status: String,
    summary: String,
    created_at: String,
}

#[derive(Clone, Debug, Deserialize)]
struct ApprovalItem {
    approval_id: Option<String>,
    proposal_id: Option<String>,
    command: String,
    #[serde(alias = "risk_level")]
    risk: String,
    status: String,
    assessment: Option<ApprovalAssessment>,
}

#[derive(Clone, Debug, Deserialize)]
struct ApprovalAssessment {
    impact: String,
    rollback: String,
    #[serde(default)]
    warnings: Vec<String>,
}

#[derive(Clone, Debug, Deserialize)]
struct RuntimeEvent {
    command_id: Option<String>,
    event_type: String,
    #[serde(default)]
    message: String,
    created_at: String,
}

#[derive(Clone, Debug, Deserialize)]
struct VerificationItem {
    target: String,
    status: String,
    passed: Option<bool>,
    #[serde(default)]
    evidence: serde_json::Value,
    #[serde(default, alias = "error")]
    detail: String,
    created_at: String,
}

#[derive(Clone, Debug, Deserialize)]
struct OrgEvent {
    event_type: String,
    created_at: String,
    #[serde(default)]
    payload: serde_json::Value,
}

#[allow(dead_code)]
#[derive(Clone, Debug, Deserialize)]
struct SwarmStatus {
    current_goal: Option<String>,
    #[serde(default)]
    plan: Vec<SwarmPlanItem>,
    #[serde(default)]
    agents: Vec<SwarmAgent>,
    #[serde(default)]
    tasks: Vec<SwarmTask>,
    #[serde(default)]
    blockers: Vec<String>,
    #[serde(default)]
    errors: Vec<String>,
    #[serde(default)]
    evidence: Vec<serde_json::Value>,
    #[serde(default)]
    memory: std::collections::HashMap<String, i64>,
}

#[allow(dead_code)]
#[derive(Clone, Debug, Deserialize)]
struct SwarmPlanItem {
    #[serde(alias = "owner")]
    role: String,
    #[serde(alias = "title")]
    task: String,
    status: String,
}

#[allow(dead_code)]
#[derive(Clone, Debug, Deserialize)]
struct SwarmAgent {
    agent_id: String,
    role: String,
    status: String,
    current_task: Option<String>,
    confidence: f32,
    risk_level: String,
    last_heartbeat: String,
}

#[allow(dead_code)]
#[derive(Clone, Debug, Deserialize)]
struct SwarmTask {
    id: String,
    title: String,
    owner: String,
    status: String,
    created_at: String,
}

#[allow(dead_code)]
#[derive(Clone, Debug, Deserialize)]
struct IncidentItem {
    severity: String,
    module: String,
    message: String,
    created_at: String,
}

#[derive(Clone, Debug, Deserialize)]
struct OrgDashboardPayload {
    health: OrgHealth,
    memory_status: OrgMemoryStatus,
    agent_ticks: Vec<AgentTick>,
    approvals: Vec<ApprovalItem>,
    approved_commands: Vec<ApprovalItem>,
    runtime_events: Vec<RuntimeEvent>,
    verifications: Vec<VerificationItem>,
    org_events: Vec<OrgEvent>,
    swarm: Option<SwarmStatus>,
    incidents: Vec<IncidentItem>,
}

#[derive(Debug, Clone)]
enum Message {
    InputChanged(String),
    Submit,
    ApiResponded(Result<ChatResponse, String>),
    StatusChecked(Result<String, String>),
    OrgDashboardLoaded(Result<OrgDashboard, String>),
    SelectPendingApproval(String),
    SelectApprovedCommand(String),
    ApproveSelected,
    ExecuteSelected,
    ApprovalCompleted(Result<String, String>),
    ExecutionCompleted(Result<String, String>),
    Tick,
}

const SCROLLABLE_ID: &str = "chat_scroll";
const HEALTH_CHECK_INTERVAL: u32 = 5;
const BG: Color = Color::from_rgb(0.035, 0.043, 0.055);
const SURFACE: Color = Color::from_rgb(0.07, 0.085, 0.105);
const SURFACE_HIGH: Color = Color::from_rgb(0.095, 0.115, 0.14);
const STROKE: Color = Color::from_rgb(0.19, 0.23, 0.28);
const TEXT_PRIMARY: Color = Color::from_rgb(0.91, 0.94, 0.96);
const TEXT_SECONDARY: Color = Color::from_rgb(0.58, 0.65, 0.72);
const TEXT_MUTED: Color = Color::from_rgb(0.38, 0.45, 0.52);
const ACCENT: Color = Color::from_rgb(0.28, 0.68, 0.96);
const SUCCESS: Color = Color::from_rgb(0.36, 0.86, 0.62);
const WARNING: Color = Color::from_rgb(0.96, 0.72, 0.28);
const DANGER: Color = Color::from_rgb(0.96, 0.32, 0.38);

impl Application for NexusApp {
    type Executor = iced::executor::Default;
    type Message = Message;
    type Theme = Theme;
    type Flags = ();

    fn new(_flags: ()) -> (Self, Command<Message>) {
        let mut system = System::new_all();
        system.refresh_all();
        (
            Self {
                input_value: String::new(),
                messages: vec![ChatMessage {
                    role: "NEXUS".to_string(),
                    content: "Neural link established. System remodeling complete.\nStanding by for high-level directives.".to_string(),
                    timestamp: current_time(),
                }],
                status: "ONLINE".to_string(),
                client: Client::new(),
                system,
                cpu_usage: 0.0,
                ram_usage: 0.0,
                is_thinking: false,
                is_playing_audio: false,
                session_start: Instant::now(),
                last_latency_ms: None,
                tick_counter: 0,
                pending_since: None,
                current_stage: "Aguardando pedido".to_string(),
                activity: vec![ActivityItem {
                    label: "Interface iniciada".to_string(),
                    detail: "Conectando ao backend local.".to_string(),
                    timestamp: current_time(),
                    level: ActivityLevel::Info,
                }],
                org: OrgDashboard::default(),
                selected_pending_proposal: None,
                selected_approved_proposal: None,
                org_action_in_flight: false,
            },
            Command::batch(vec![
                Command::perform(check_status(), Message::StatusChecked),
                Command::perform(load_org_dashboard(), Message::OrgDashboardLoaded),
            ]),
        )
    }

    fn title(&self) -> String {
        String::from("NEXUS — Neural Command HUD")
    }

    fn update(&mut self, message: Message) -> Command<Message> {
        match message {
            Message::Tick => {
                self.tick_counter += 1;
                self.system.refresh_cpu();
                self.system.refresh_memory();
                self.cpu_usage = self.system.global_cpu_info().cpu_usage();
                self.ram_usage =
                    (self.system.used_memory() as f32 / self.system.total_memory() as f32) * 100.0;
                if self.is_thinking {
                    self.current_stage = self.processing_stage();
                }
                if self.tick_counter % HEALTH_CHECK_INTERVAL == 0 {
                    return Command::batch(vec![
                        Command::perform(check_status(), Message::StatusChecked),
                        Command::perform(load_org_dashboard(), Message::OrgDashboardLoaded),
                    ]);
                }
                Command::none()
            }
            Message::InputChanged(val) => {
                self.input_value = val;
                Command::none()
            }
            Message::Submit => {
                if self.input_value.trim().is_empty() || self.is_thinking {
                    return Command::none();
                }
                let user_text = self.input_value.clone();
                self.messages.push(ChatMessage {
                    role: "OPERATOR".to_string(),
                    content: user_text.clone(),
                    timestamp: current_time(),
                });
                self.input_value.clear();
                self.is_thinking = true;
                self.pending_since = Some(Instant::now());
                self.current_stage = "Pedido enviado ao backend".to_string();
                self.push_activity(
                    "Pedido enviado",
                    "Aguardando resposta do agente. Nenhuma acao e assumida como feita ate o backend confirmar.",
                    ActivityLevel::Info,
                );
                Command::batch(vec![
                    Command::perform(
                        send_message(self.client.clone(), user_text),
                        Message::ApiResponded,
                    ),
                    scrollable::snap_to(
                        scrollable::Id::new(SCROLLABLE_ID),
                        scrollable::RelativeOffset::END,
                    ),
                ])
            }
            Message::ApiResponded(Ok(response)) => {
                self.is_thinking = false;
                self.pending_since = None;
                self.current_stage = "Resposta recebida".to_string();
                self.last_latency_ms = response.latency_ms;
                let request_id = response.id.as_deref().unwrap_or("sem id");
                let detail = response
                    .latency_ms
                    .map(|ms| format!("Backend respondeu em {}ms. id={}", ms, request_id))
                    .unwrap_or_else(|| {
                        format!(
                            "Backend respondeu sem metrica de latencia. id={}",
                            request_id
                        )
                    });
                self.push_activity("Resposta recebida", &detail, ActivityLevel::Success);
                self.messages.push(ChatMessage {
                    role: "NEXUS".to_string(),
                    content: response.reply.clone(),
                    timestamp: current_time(),
                });
                if let Some(audio_b64) = response.audio {
                    if !audio_b64.is_empty() {
                        self.is_playing_audio = true;
                        let audio_detail = response
                            .audio_mime
                            .as_deref()
                            .map(|mime| {
                                format!("Audio {} recebido; reproduzindo resposta local.", mime)
                            })
                            .unwrap_or_else(|| {
                                "Audio recebido; reproduzindo resposta local.".to_string()
                            });
                        self.push_activity("Voz", &audio_detail, ActivityLevel::Info);
                        let _ = play_audio(audio_b64);
                    }
                }
                scrollable::snap_to(
                    scrollable::Id::new(SCROLLABLE_ID),
                    scrollable::RelativeOffset::END,
                )
            }
            Message::ApiResponded(Err(e)) => {
                self.is_thinking = false;
                self.pending_since = None;
                self.current_stage = "Falha na requisicao".to_string();
                self.push_activity("Falha", &e, ActivityLevel::Error);
                self.messages.push(ChatMessage {
                    role: "CORE_ERROR".to_string(),
                    content: format!("Nao consegui concluir a requisicao.\n\n{}", e),
                    timestamp: current_time(),
                });
                scrollable::snap_to(
                    scrollable::Id::new(SCROLLABLE_ID),
                    scrollable::RelativeOffset::END,
                )
            }
            Message::StatusChecked(Ok(status)) => {
                if self.status != status {
                    self.push_activity(
                        "Backend online",
                        "Health check local respondeu com sucesso.",
                        ActivityLevel::Success,
                    );
                }
                self.status = status;
                self.is_playing_audio = false;
                Command::none()
            }
            Message::StatusChecked(Err(_)) => {
                if self.status != "OFFLINE" {
                    self.push_activity(
                        "Backend offline",
                        "Nao foi possivel acessar http://127.0.0.1:8080/api/health.",
                        ActivityLevel::Error,
                    );
                }
                self.status = "OFFLINE".to_string();
                self.is_playing_audio = false;
                Command::none()
            }
            Message::OrgDashboardLoaded(Ok(mut dashboard)) => {
                let previous_status = self.org.health.as_ref().map(|health| health.status.clone());
                let next_status = dashboard
                    .health
                    .as_ref()
                    .map(|health| health.status.clone());
                dashboard.updated_at = Some(current_time());
                dashboard.error = None;

                if previous_status != next_status {
                    if let Some(status) = next_status.as_deref() {
                        self.push_activity(
                            "Organizacao atualizada",
                            &format!("Daemon organizacional reportou estado {}.", status),
                            if status == "running" {
                                ActivityLevel::Success
                            } else {
                                ActivityLevel::Warning
                            },
                        );
                    }
                }

                self.org = dashboard;
                Command::none()
            }
            Message::OrgDashboardLoaded(Err(error)) => {
                if self.org.error.as_deref() != Some(error.as_str()) {
                    self.push_activity(
                        "Painel organizacional",
                        &format!("Falha ao ler estado real: {}", error),
                        ActivityLevel::Warning,
                    );
                }
                self.org.error = Some(error);
                self.org.updated_at = Some(current_time());
                Command::none()
            }
            Message::SelectPendingApproval(proposal_id) => {
                self.selected_pending_proposal = Some(proposal_id);
                Command::none()
            }
            Message::SelectApprovedCommand(proposal_id) => {
                self.selected_approved_proposal = Some(proposal_id);
                Command::none()
            }
            Message::ApproveSelected => {
                if self.org_action_in_flight {
                    return Command::none();
                }
                let Some(proposal_id) = self.selected_pending_proposal.clone() else {
                    return Command::none();
                };
                self.org_action_in_flight = true;
                self.push_activity(
                    "Aprovacao solicitada",
                    &format!(
                        "GUI vai aprovar uma vez a proposta {}. Nenhuma execucao sera iniciada.",
                        short_id(&proposal_id)
                    ),
                    ActivityLevel::Warning,
                );
                Command::perform(approve_org_command(proposal_id), Message::ApprovalCompleted)
            }
            Message::ExecuteSelected => {
                if self.org_action_in_flight {
                    return Command::none();
                }
                let Some(proposal_id) = self.selected_approved_proposal.clone() else {
                    return Command::none();
                };
                self.org_action_in_flight = true;
                self.push_activity(
                    "Execucao solicitada",
                    &format!(
                        "Runtime vai executar comando ja aprovado {} e registrar evidencias.",
                        short_id(&proposal_id)
                    ),
                    ActivityLevel::Warning,
                );
                Command::perform(
                    execute_org_command(proposal_id),
                    Message::ExecutionCompleted,
                )
            }
            Message::ApprovalCompleted(Ok(detail)) => {
                self.org_action_in_flight = false;
                self.selected_pending_proposal = None;
                self.push_activity("Comando aprovado", &detail, ActivityLevel::Success);
                Command::perform(load_org_dashboard(), Message::OrgDashboardLoaded)
            }
            Message::ApprovalCompleted(Err(error)) => {
                self.org_action_in_flight = false;
                self.push_activity("Falha ao aprovar", &error, ActivityLevel::Error);
                Command::none()
            }
            Message::ExecutionCompleted(Ok(detail)) => {
                self.org_action_in_flight = false;
                self.selected_approved_proposal = None;
                self.push_activity("Execucao validada", &detail, ActivityLevel::Success);
                Command::perform(load_org_dashboard(), Message::OrgDashboardLoaded)
            }
            Message::ExecutionCompleted(Err(error)) => {
                self.org_action_in_flight = false;
                self.push_activity("Falha na execucao", &error, ActivityLevel::Error);
                Command::perform(load_org_dashboard(), Message::OrgDashboardLoaded)
            }
        }
    }

    fn subscription(&self) -> Subscription<Message> {
        iced::time::every(Duration::from_millis(1000)).map(|_| Message::Tick)
    }

    fn view(&self) -> Element<'_, Message> {
        let uptime = self.session_start.elapsed();
        let uptime_str = format!(
            "UPTIME: {}m {}s",
            uptime.as_secs() / 60,
            uptime.as_secs() % 60
        );

        let is_online = self.status == "ONLINE";
        let status_pill = container(
            Row::new()
                .spacing(8)
                .align_items(Alignment::Center)
                .push(container(Space::new(8, 8)).style(if is_online { success_dot_style } else { danger_dot_style }))
                .push(text(&self.status).size(12).style(TEXT_PRIMARY)),
        )
        .padding([4, 12])
        .style(status_pill_style);

        let header = container(
            Row::new()
                .spacing(24)
                .align_items(Alignment::Center)
                .push(
                    Column::new()
                        .push(text("NEXUS").size(24).style(TEXT_PRIMARY))
                        .push(
                            text(format!("NEURAL COMMAND HUD · {}", uptime_str))
                                .size(10)
                                .style(TEXT_MUTED),
                        ),
                )
                .push(Space::with_width(Length::Fill))
                .push(telemetry_item(
                    "CPU",
                    format!("{:.1}%", self.cpu_usage),
                    self.cpu_usage > 80.0,
                ))
                .push(telemetry_item(
                    "RAM",
                    format!("{:.1}%", self.ram_usage),
                    self.ram_usage > 85.0,
                ))
                .push(status_pill),
        )
        .padding([16, 32])
        .style(header_style);

        let body = Row::new()
            .push(
                container(self.chat_panel())
                    .width(Length::FillPortion(2))
                    .style(panel_style),
            )
            .push(
                container(self.swarm_dashboard())
                    .width(Length::FillPortion(3))
                    .style(panel_center_style),
            )
            .push(
                container(self.ops_panel())
                    .width(Length::FillPortion(2))
                    .style(panel_style),
            );

        let footer = container(
            Row::new()
                .spacing(16)
                .align_items(Alignment::Center)
                .push(
                    text("DIRECTIVE:")
                        .size(12)
                        .style(ACCENT)
                        .width(80),
                )
                .push(
                    text_input("TRANSMIT DIRECTIVE TO CORE...", &self.input_value)
                        .on_input(Message::InputChanged)
                        .on_submit(Message::Submit)
                        .padding(12)
                )
                .push(
                    {
                        let mut btn = button(text("TRANSMIT").size(14))
                            .padding([10, 24]);
                        if !self.is_thinking {
                            btn = btn.on_press(Message::Submit);
                        }
                        btn
                    }
                ),
        )
        .padding([20, 32])
        .style(footer_style);

        container(
            Column::new()
                .push(header)
                .push(Rule::horizontal(1).style(rule_style))
                .push(body.height(Length::Fill))
                .push(Rule::horizontal(1).style(rule_style))
                .push(footer),
        )
        .width(Length::Fill)
        .height(Length::Fill)
        .style(app_shell_style)
        .into()
    }

    fn theme(&self) -> Theme {
        Theme::Dark
    }
}

impl NexusApp {
    fn chat_panel(&self) -> Element<'_, Message> {
        let mut chat_col = Column::new()
            .spacing(16)
            .padding(24);

        for msg in &self.messages {
            let is_nexus = msg.role == "NEXUS";
            
            chat_col = chat_col.push(
                Column::new()
                    .spacing(4)
                    .push(text(&msg.role).size(10).style(TEXT_MUTED))
                    .push(
                        container(text(&msg.content).size(14).style(TEXT_PRIMARY))
                            .padding(14)
                            .width(Length::Fill)
                            .style(if is_nexus { chat_msg_nexus_style } else { chat_msg_user_style })
                    )
            );
        }

        if self.is_thinking {
            chat_col = chat_col.push(
                text(self.processing_stage())
                    .size(12)
                    .style(ACCENT)
            );
        }

        scrollable(chat_col)
            .id(scrollable::Id::new(SCROLLABLE_ID))
            .height(Length::Fill)
            .into()
    }

    fn swarm_dashboard(&self) -> Element<'_, Message> {
        let mut agents_grid = Row::new().spacing(16);
        
        if let Some(swarm) = &self.org.swarm {
            let mut col1 = Column::new().spacing(16).width(Length::Fill);
            let mut col2 = Column::new().spacing(16).width(Length::Fill);
            
            for (i, agent) in swarm.agents.iter().enumerate() {
                let card = self.agent_card(agent);
                if i % 2 == 0 {
                    col1 = col1.push(card);
                } else {
                    col2 = col2.push(card);
                }
            }
            agents_grid = agents_grid.push(col1).push(col2);
        } else {
            agents_grid = agents_grid.push(text("Aguardando conexao com o Swarm...").style(TEXT_MUTED));
        }

        Column::new()
            .spacing(24)
            .padding(24)
            .push(text("SWARM ORCHESTRATION").size(14).style(TEXT_PRIMARY))
            .push(scrollable(agents_grid).height(Length::Fill))
            .into()
    }

    fn agent_card(&self, agent: &SwarmAgent) -> Element<'_, Message> {
        let status_color = match agent.status.as_str() {
            "assigned" | "running" => SUCCESS,
            "idle" => TEXT_MUTED,
            _ => ACCENT,
        };

        container(
            Column::new()
                .spacing(10)
                .push(
                    Row::new()
                        .spacing(12)
                        .align_items(Alignment::Center)
                        .push(text(&agent.role.to_uppercase()).size(12).style(ACCENT))
                        .push(Space::with_width(Length::Fill))
                        .push(
                            container(text(&agent.status).size(9).style(status_color))
                                .padding([2, 8])
                                .style(status_pill_style)
                        )
                )
                .push(
                    text(agent.current_task.as_deref().unwrap_or("Waiting for assignment..."))
                        .size(11)
                        .style(TEXT_PRIMARY)
                )
                .push(
                    Row::new()
                        .spacing(8)
                        .align_items(Alignment::Center)
                        .push(text(format!("{:.0}%", agent.confidence * 100.0)).size(10).style(TEXT_MUTED))
                        .push(container(Space::with_width(Length::Fill).height(2)).style(confidence_bar_style))
                )
        )
        .padding(16)
        .style(agent_card_style)
        .into()
    }

    fn ops_panel(&self) -> Element<'_, Message> {
        let mut plan_col = Column::new().spacing(10);
        if let Some(swarm) = &self.org.swarm {
            for item in swarm.plan.iter().take(6) {
                plan_col = plan_col.push(
                    Row::new()
                        .spacing(10)
                        .push(text(&item.role).size(10).width(60).style(ACCENT))
                        .push(text(&item.task).size(10).width(Length::Fill).style(TEXT_PRIMARY))
                );
            }
        }

        let mut incident_col = Column::new().spacing(8);
        for inc in self.org.incidents.iter().take(3) {
            incident_col = incident_col.push(
                text(format!("[{}] {}", inc.severity, inc.message))
                    .size(10)
                    .style(DANGER)
            );
        }

        scrollable(
            Column::new()
                .spacing(24)
                .padding(24)
                .push(text("STRATEGY PLAN").size(12).style(TEXT_SECONDARY))
                .push(plan_col)
                .push(Rule::horizontal(1).style(rule_style))
                .push(text("INCIDENTS").size(12).style(DANGER))
                .push(incident_col)
                .push(Rule::horizontal(1).style(rule_style))
                .push(self.activity_panel_compact())
        )
        .height(Length::Fill)
        .into()
    }

    fn activity_panel_compact(&self) -> Element<'_, Message> {
        let mut col = Column::new().spacing(8);
        col = col.push(text("ACTIVITY LOG").size(12).style(TEXT_SECONDARY));
        for item in self.visible_activity().iter().rev().take(5) {
            col = col.push(
                text(format!("{} {}", trim_text(&item.timestamp, 8), item.label))
                    .size(10)
                    .style(TEXT_MUTED)
            );
        }
        col.into()
    }

    fn push_activity(&mut self, label: &str, detail: &str, level: ActivityLevel) {
        self.activity.push(ActivityItem {
            label: label.to_string(),
            detail: detail.to_string(),
            timestamp: current_time(),
            level,
        });
        if self.activity.len() > 12 {
            let drain_count = self.activity.len() - 12;
            self.activity.drain(0..drain_count);
        }
    }

    fn processing_stage(&self) -> String {
        let elapsed = self
            .pending_since
            .map(|start| start.elapsed().as_secs())
            .unwrap_or(0);
        match elapsed {
            0..=2 => "Recebido. Preparando contexto e memoria da conversa.".to_string(),
            3..=7 => "Agente em execucao. Aguardando resposta verificavel do backend.".to_string(),
            8..=15 => "Ainda trabalhando. Se houver acao real, ela precisa aparecer como resultado ou aprovacao.".to_string(),
            _ => "Demorando mais que o normal. O pedido continua pendente no backend local.".to_string(),
        }
    }

    fn visible_activity(&self) -> Vec<ActivityItem> {
        let mut items = self.activity.clone();
        if self
            .pending_since
            .map(|start| start.elapsed().as_secs() > 15)
            .unwrap_or(false)
        {
            items.push(ActivityItem {
                label: "Atraso percebido".to_string(),
                detail: "A requisicao ainda nao voltou. O estado continua pendente, nao concluido."
                    .to_string(),
                timestamp: current_time(),
                level: ActivityLevel::Warning,
            });
        }
        items
    }

    fn selected_pending_approval(&self) -> Option<&ApprovalItem> {
        let selected = self.selected_pending_proposal.as_deref()?;
        self.org
            .approvals
            .iter()
            .find(|item| approval_proposal_id(item) == selected)
    }

    fn selected_approved_command(&self) -> Option<&ApprovalItem> {
        let selected = self.selected_approved_proposal.as_deref()?;
        self.org
            .approved_commands
            .iter()
            .find(|item| approval_proposal_id(item) == selected)
    }

    fn approval_detail_card(
        &self,
        label: &'static str,
        approval: &ApprovalItem,
        action: Option<Message>,
        action_label: &'static str,
    ) -> Element<'_, Message> {
        let assessment = approval.assessment.as_ref();
        let warnings = assessment
            .map(|item| item.warnings.join(", "))
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| "sem avisos adicionais".to_string());
        let mut content = Column::new()
            .spacing(6)
            .push(text(label).size(10).style(Color::from_rgb8(170, 185, 200)))
            .push(
                text(trim_text(&approval.command, 72))
                    .size(11)
                    .style(Color::from_rgb8(230, 236, 242)),
            )
            .push(
                text(format!(
                    "Impacto: {}",
                    trim_text(
                        assessment
                            .map(|item| item.impact.as_str())
                            .unwrap_or("impacto nao informado"),
                        72,
                    )
                ))
                .size(10)
                .style(Color::from_rgb8(150, 165, 180)),
            )
            .push(
                text(format!(
                    "Rollback: {}",
                    trim_text(
                        assessment
                            .map(|item| item.rollback.as_str())
                            .unwrap_or("rollback nao informado"),
                        72,
                    )
                ))
                .size(10)
                .style(Color::from_rgb8(150, 165, 180)),
            )
            .push(
                text(format!("Avisos: {}", trim_text(&warnings, 72)))
                    .size(10)
                    .style(Color::from_rgb8(255, 200, 90)),
            );

        let mut action_button = button(text(action_label).size(11));
        if !self.org_action_in_flight {
            if let Some(message) = action {
                action_button = action_button.on_press(message);
            }
        }
        content = content.push(action_button);

        container(content)
            .padding(10)
            .width(Length::Fill)
            .style(activity_item_style)
            .into()
    }
}

fn metric_row<'a>(label: &'static str, value: String) -> Row<'a, Message> {
    Row::new()
        .align_items(Alignment::Center)
        .push(text(label).size(12).style(TEXT_SECONDARY))
        .push(Space::with_width(Length::Fill))
        .push(text(value).size(12).style(TEXT_PRIMARY))
}

fn ops_metric<'a>(label: &'static str, value: String, alert: bool) -> Column<'a, Message> {
    let value_color = if alert { WARNING } else { TEXT_PRIMARY };
    Column::new()
        .spacing(3)
        .width(Length::FillPortion(1))
        .push(text(label).size(10).style(TEXT_MUTED))
        .push(
            container(text(value).size(12).style(value_color))
                .padding([8, 10])
                .width(Length::Fill)
                .style(metric_card_style),
        )
}

fn telemetry_item<'a>(label: &'static str, val: String, alert: bool) -> Column<'a, Message> {
    let val_color = if alert { DANGER } else { TEXT_PRIMARY };
    Column::new()
        .spacing(3)
        .push(text(label).size(10).style(TEXT_MUTED))
        .push(
            container(text(val).size(16).style(val_color))
                .padding([8, 12])
                .style(metric_card_style),
        )
}

fn current_time() -> String {
    chrono::Local::now().format("%H:%M:%S").to_string()
}

fn short_id(value: &str) -> String {
    value.chars().take(10).collect()
}

fn trim_text(value: &str, max_chars: usize) -> String {
    if value.chars().count() <= max_chars {
        return value.to_string();
    }
    let mut trimmed: String = value.chars().take(max_chars.saturating_sub(3)).collect();
    trimmed.push_str("...");
    trimmed
}

fn compact_json(value: &serde_json::Value, max_chars: usize) -> String {
    if value.is_null() {
        return String::new();
    }
    trim_text(&value.to_string(), max_chars)
}

fn approval_proposal_id(approval: &ApprovalItem) -> String {
    approval
        .proposal_id
        .as_deref()
        .or(approval.approval_id.as_deref())
        .unwrap_or("sem id")
        .to_string()
}

fn approval_impact_line(approval: &ApprovalItem) -> String {
    approval
        .assessment
        .as_ref()
        .map(|item| trim_text(&item.impact, 38))
        .unwrap_or_else(|| "impacto nao informado".to_string())
}

fn verification_evidence_line(verification: &VerificationItem) -> String {
    if !verification.detail.is_empty() {
        return verification.detail.clone();
    }
    let stdout = verification
        .evidence
        .get("stdout_tail")
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .trim();
    let stderr = verification
        .evidence
        .get("stderr_tail")
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .trim();
    if !stdout.is_empty() {
        return format!("stdout: {}", stdout);
    }
    if !stderr.is_empty() {
        return format!("stderr: {}", stderr);
    }
    "sem evidencia textual curta".to_string()
}

fn play_audio(base64_data: String) -> Result<(), Box<dyn std::error::Error>> {
    use base64::{engine::general_purpose, Engine as _};
    let audio_bytes = general_purpose::STANDARD.decode(base64_data)?;
    std::thread::spawn(move || {
        if let Ok((_stream, stream_handle)) = OutputStream::try_default() {
            if let Ok(sink) = Sink::try_new(&stream_handle) {
                let cursor = Cursor::new(audio_bytes);
                if let Ok(source) = Decoder::new(cursor) {
                    sink.append(source);
                    sink.sleep_until_end();
                }
            }
        }
    });
    Ok(())
}

fn app_shell_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(BG.into()),
        text_color: Some(TEXT_PRIMARY),
        ..Default::default()
    }
}
fn hud_top_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.055, 0.068, 0.085).into()),
        border: Border {
            color: STROKE,
            width: 0.0,
            radius: 0.0.into(),
        },
        ..Default::default()
    }
}
fn bottom_bar_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(SURFACE.into()),
        border: Border {
            color: STROKE,
            width: 1.0,
            radius: 0.0.into(),
        },
        ..Default::default()
    }
}
fn input_field_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(SURFACE_HIGH.into()),
        border: Border {
            color: STROKE,
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn transmit_btn_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(ACCENT.into()),
        border: Border {
            color: Color::from_rgb(0.48, 0.78, 1.0),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn nexus_bubble_modern(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(SURFACE_HIGH.into()),
        border: Border {
            color: Color::from_rgb(0.24, 0.39, 0.52),
            width: 1.0,
            radius: [8.0, 8.0, 8.0, 2.0].into(),
        },
        ..Default::default()
    }
}
fn operator_bubble_modern(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.16, 0.135, 0.095).into()),
        border: Border {
            color: Color::from_rgb(0.66, 0.52, 0.28),
            width: 1.0,
            radius: [8.0, 8.0, 2.0, 8.0].into(),
        },
        ..Default::default()
    }
}
fn error_bubble_modern(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.19, 0.08, 0.095).into()),
        border: Border {
            color: DANGER,
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn progress_bubble_modern(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.12, 0.15, 0.19).into()),
        border: Border {
            color: ACCENT,
            width: 1.0,
            radius: [8.0, 8.0, 8.0, 2.0].into(),
        },
        ..Default::default()
    }
}
fn side_panel_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.055, 0.068, 0.085).into()),
        border: Border {
            color: STROKE,
            width: 1.0,
            radius: 0.0.into(),
        },
        ..Default::default()
    }
}
fn side_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(SURFACE.into()),
        border: Border {
            color: STROKE,
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn ops_console_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(SURFACE.into()),
        border: Border {
            color: STROKE,
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn activity_item_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(SURFACE_HIGH.into()),
        border: Border {
            color: Color::from_rgb(0.16, 0.20, 0.25),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn info_activity_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(ACCENT.into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
fn success_activity_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(SUCCESS.into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
fn warning_activity_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(WARNING.into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
fn error_activity_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(DANGER.into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
fn success_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(SUCCESS.into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
fn error_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(DANGER.into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}

fn status_pill_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.075, 0.095, 0.12).into()),
        border: Border {
            color: STROKE,
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn metric_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.06, 0.075, 0.095).into()),
        border: Border {
            color: Color::from_rgb(0.14, 0.18, 0.22),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn header_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.04, 0.05, 0.06).into()),
        ..Default::default()
    }
}

fn panel_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.03, 0.04, 0.05).into()),
        ..Default::default()
    }
}

fn panel_center_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.02, 0.03, 0.04).into()),
        ..Default::default()
    }
}

fn footer_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.04, 0.05, 0.06).into()),
        ..Default::default()
    }
}

fn chat_msg_user_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.08, 0.1, 0.12).into()),
        border: Border {
            color: Color::from_rgb(0.15, 0.18, 0.22),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn chat_msg_nexus_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.05, 0.07, 0.09).into()),
        border: Border {
            color: ACCENT,
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn agent_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.06, 0.08, 0.1).into()),
        border: Border {
            color: Color::from_rgb(0.12, 0.15, 0.18),
            width: 1.0,
            radius: 10.0.into(),
        },
        ..Default::default()
    }
}


fn btn_primary_style(_theme: &Theme) -> button::Appearance {
    button::Appearance {
        background: Some(ACCENT.into()),
        border: Border {
            radius: 6.0.into(),
            ..Default::default()
        },
        text_color: Color::WHITE,
        ..Default::default()
    }
}

fn btn_disabled_style(_theme: &Theme) -> button::Appearance {
    button::Appearance {
        background: Some(Color::from_rgb(0.1, 0.12, 0.15).into()),
        border: Border {
            radius: 6.0.into(),
            ..Default::default()
        },
        text_color: Color::from_rgb(0.4, 0.4, 0.4),
        ..Default::default()
    }
}



fn rule_style(_theme: &Theme) -> iced::widget::rule::Appearance {
    iced::widget::rule::Appearance {
        color: Color::from_rgb(0.1, 0.12, 0.15),
        width: 1,
        radius: 0.0.into(),
        fill_mode: iced::widget::rule::FillMode::Full,
    }
}

async fn check_status() -> Result<String, String> {
    let resp = reqwest::get("http://127.0.0.1:8080/api/health")
        .await
        .map_err(|_| "OFFLINE".to_string())?;
    if resp.status().is_success() {
        Ok("ONLINE".to_string())
    } else {
        Err("API ERROR".to_string())
    }
}

async fn load_org_dashboard() -> Result<OrgDashboard, String> {
    let payload = run_org_json::<OrgDashboardPayload>(&["dashboard"]).await?;

    Ok(OrgDashboard {
        health: Some(payload.health),
        memory: Some(payload.memory_status),
        agent_ticks: payload.agent_ticks,
        approvals: payload.approvals,
        approved_commands: payload.approved_commands,
        runtime_events: payload.runtime_events,
        verifications: payload.verifications,
        org_events: payload.org_events,
        swarm: payload.swarm,
        incidents: payload.incidents,
        updated_at: Some(current_time()),
        error: None,
    })
}

async fn run_org_json<T: DeserializeOwned>(args: &[&str]) -> Result<T, String> {
    let root = project_root();
    let bin = root.join("bin").join("nexus");
    let output = TokioCommand::new(&bin)
        .arg("org")
        .args(args)
        .current_dir(&root)
        .output()
        .await
        .map_err(|error| format!("{}: {}", bin.display(), error))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let detail = if !stderr.is_empty() { stderr } else { stdout };
        return Err(format!("org {} falhou: {}", args.join(" "), detail));
    }

    serde_json::from_slice(&output.stdout)
        .map_err(|error| format!("json invalido em org {}: {}", args.join(" "), error))
}

async fn approve_org_command(proposal_id: String) -> Result<String, String> {
    let payload = run_org_json::<serde_json::Value>(&[
        "approve-command",
        &proposal_id,
        "--approved-by",
        "iced_gui",
        "--scope",
        "once",
    ])
    .await?;
    let approval_id = payload
        .get("approval_id")
        .and_then(|value| value.as_str())
        .unwrap_or("sem approval_id");
    Ok(format!(
        "Proposta {} aprovada uma vez. approval_id={}",
        short_id(&proposal_id),
        short_id(approval_id)
    ))
}

async fn execute_org_command(proposal_id: String) -> Result<String, String> {
    let payload = run_org_json::<serde_json::Value>(&[
        "execute-command",
        &proposal_id,
        "--agent",
        "gui-iced",
        "--timeout-s",
        "30",
    ])
    .await?;
    let command_id = payload
        .get("command_id")
        .and_then(|value| value.as_str())
        .or_else(|| payload.get("command_id").and_then(|value| value.as_str()))
        .unwrap_or("sem command_id");
    let status = payload
        .get("status")
        .and_then(|value| value.as_str())
        .unwrap_or("status desconhecido");
    let verification = payload
        .get("verification")
        .and_then(|value| value.get("status"))
        .and_then(|value| value.as_str())
        .unwrap_or("sem verificacao");
    let detail = format!(
        "Proposta {} executada. command_id={} status={} verificacao={}",
        short_id(&proposal_id),
        short_id(command_id),
        status,
        verification
    );
    if status == "executed" && verification == "passed" {
        Ok(detail)
    } else {
        Err(detail)
    }
}

fn danger_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(DANGER.into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}

fn confidence_bar_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.1, 0.12, 0.15).into()),
        ..Default::default()
    }
}

fn project_root() -> PathBuf {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if cwd
        .file_name()
        .and_then(|name| name.to_str())
        .map(|name| name == "nexus-iced")
        .unwrap_or(false)
    {
        cwd.parent()
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("."))
    } else {
        cwd
    }
}

#[derive(Serialize)]
struct ChatPayload {
    message: String,
    client_id: String,
    voice_response: bool,
}
#[derive(Deserialize, Debug, Clone)]
struct ChatResponse {
    reply: String,
    audio: Option<String>,
    latency_ms: Option<u64>,
    id: Option<String>,
    audio_mime: Option<String>,
}
async fn send_message(client: Client, message: String) -> Result<ChatResponse, String> {
    let payload = ChatPayload {
        message,
        client_id: "iced_gui_v4_remodeled".to_string(),
        voice_response: true,
    };
    let resp = client
        .post("http://127.0.0.1:8080/api/applet/chat")
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Falha de rede: {}", e))?;
    let status = resp.status();
    if !status.is_success() {
        let body = resp.text().await.unwrap_or_else(|_| String::new());
        return Err(format!("Backend retornou {}. {}", status, body));
    }
    let json: ChatResponse = resp
        .json()
        .await
        .map_err(|e| format!("Resposta invalida do backend: {}", e))?;
    Ok(json)
}
