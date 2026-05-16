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
    #[serde(alias = "agent_role", alias = "id")]
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
        let status_color = if is_online {
            Color::from_rgb8(0, 255, 136)
        } else {
            Color::from_rgb8(255, 60, 80)
        };

        let mut hud_row = Row::new()
            .spacing(28)
            .align_items(Alignment::Center)
            .push(
                Column::new()
                    .push(
                        text("NEXUS CORE")
                            .size(16)
                            .style(Color::from_rgb8(220, 230, 238)),
                    )
                    .push(
                        text(&uptime_str)
                            .size(11)
                            .style(Color::from_rgb8(132, 145, 160)),
                    ),
            )
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
            .push(
                Column::new()
                    .push(
                        text("SYNAPSE STATUS")
                            .size(10)
                            .style(Color::from_rgb8(100, 100, 120)),
                    )
                    .push(
                        Row::new()
                            .spacing(6)
                            .align_items(Alignment::Center)
                            .push(
                                container(iced::widget::Space::with_width(8))
                                    .width(8)
                                    .height(8)
                                    .style(if is_online {
                                        success_dot_style
                                    } else {
                                        error_dot_style
                                    }),
                            )
                            .push(text(&self.status).size(16).style(status_color)),
                    ),
            )
            .push(
                Column::new()
                    .push(
                        text("ESTADO ATUAL")
                            .size(10)
                            .style(Color::from_rgb8(100, 100, 120)),
                    )
                    .push(
                        text(&self.current_stage)
                            .size(15)
                            .style(Color::from_rgb8(230, 236, 242)),
                    ),
            )
            .push(
                Column::new()
                    .push(
                        text("LATENCIA")
                            .size(10)
                            .style(Color::from_rgb8(100, 100, 120)),
                    )
                    .push(
                        text(
                            self.last_latency_ms
                                .map(|ms| format!("{}ms", ms))
                                .unwrap_or_else(|| "---".into()),
                        )
                        .size(16)
                        .style(Color::from_rgb8(112, 224, 180)),
                    ),
            );

        if self.is_playing_audio {
            hud_row = hud_row.push(
                text("VOZ ATIVA")
                    .size(12)
                    .style(Color::from_rgb8(255, 200, 50)),
            );
        }

        let hud_top = container(hud_row.padding([18, 22]))
            .width(Length::Fill)
            .style(hud_top_style);

        let mut messages_column =
            self.messages
                .iter()
                .fold(Column::new().spacing(18).padding(24), |col, msg| {
                    let is_nexus = msg.role == "NEXUS";
                    let is_error = msg.role == "CORE_ERROR";
                    let align = if is_nexus {
                        Alignment::Start
                    } else {
                        Alignment::End
                    };
                    let bubble_style = if is_nexus {
                        nexus_bubble_modern
                    } else if is_error {
                        error_bubble_modern
                    } else {
                        operator_bubble_modern
                    };
                    let role_color = if is_nexus {
                        Color::from_rgb8(0, 240, 255)
                    } else if is_error {
                        Color::from_rgb8(255, 60, 80)
                    } else {
                        Color::from_rgb8(255, 200, 50)
                    };

                    col.push(
                        Column::new()
                            .spacing(8)
                            .align_items(align)
                            .push(
                                Row::new()
                                    .spacing(10)
                                    .push(text(&msg.role).size(11).style(role_color))
                                    .push(
                                        text(&msg.timestamp)
                                            .size(10)
                                            .style(Color::from_rgb8(60, 60, 80)),
                                    ),
                            )
                            .push(
                                container(text(&msg.content).size(15))
                                    .padding([14, 18])
                                    .max_width(700.0)
                                    .style(bubble_style),
                            ),
                    )
                });

        if self.is_thinking {
            let elapsed = self
                .pending_since
                .map(|start| format!("{}s", start.elapsed().as_secs()))
                .unwrap_or_else(|| "0s".to_string());
            messages_column = messages_column.push(
                Column::new()
                    .spacing(8)
                    .align_items(Alignment::Start)
                    .push(
                        Row::new()
                            .spacing(10)
                            .push(text("NEXUS").size(11).style(Color::from_rgb8(0, 240, 255)))
                            .push(
                                text(format!("processando ha {}", elapsed))
                                    .size(10)
                                    .style(Color::from_rgb8(132, 145, 160)),
                            ),
                    )
                    .push(
                        container(text(self.processing_stage()).size(15))
                            .padding([14, 18])
                            .max_width(700.0)
                            .style(progress_bubble_modern),
                    ),
            );
        }

        let chat_scroll = scrollable(messages_column)
            .id(scrollable::Id::new(SCROLLABLE_ID))
            .height(Length::Fill)
            .width(Length::Fill);

        let dots = match self.tick_counter % 4 {
            0 => ".  ",
            1 => ".. ",
            2 => "...",
            _ => "   ",
        };
        let input_placeholder = if self.is_thinking {
            format!("NEURAL PROCESSING IN PROGRESS{}", dots)
        } else {
            "TRANSMIT DIRECTIVE TO CORE...".into()
        };

        let input_field = text_input(&input_placeholder, &self.input_value)
            .on_input(Message::InputChanged)
            .on_submit(Message::Submit)
            .padding(15)
            .size(16);

        let mut transmit_btn = button(
            container(
                text(if self.is_thinking {
                    "AGUARDE"
                } else {
                    "ENVIAR"
                })
                .size(14)
                .style(Color::WHITE),
            )
            .padding([12, 24])
            .style(transmit_btn_style),
        );
        if !self.is_thinking {
            transmit_btn = transmit_btn.on_press(Message::Submit);
        }

        let bottom_bar = container(
            Row::new()
                .spacing(14)
                .align_items(Alignment::Center)
                .push(
                    container(input_field)
                        .width(Length::Fill)
                        .style(input_field_style),
                )
                .push(transmit_btn)
                .padding(18),
        )
        .width(Length::Fill)
        .style(bottom_bar_style);

        let activity_panel = self.activity_panel();
        let left_pane = Column::new()
            .push(self.operations_console())
            .push(chat_scroll)
            .height(Length::Fill)
            .width(Length::Fill);

        let body = Row::new()
            .push(left_pane)
            .push(activity_panel)
            .height(Length::Fill);

        Column::new()
            .push(hud_top)
            .push(Rule::horizontal(1))
            .push(body)
            .push(bottom_bar)
            .into()
    }

    fn theme(&self) -> Theme {
        Theme::Dark
    }
}

impl NexusApp {
    fn push_activity(&mut self, label: &str, detail: &str, level: ActivityLevel) {
        self.activity.push(ActivityItem {
            label: label.to_string(),
            detail: detail.to_string(),
            timestamp: current_time(),
            level,
        });
        if self.activity.len() > 8 {
            let drain_count = self.activity.len() - 8;
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

    fn operations_console(&self) -> Element<'_, Message> {
        let health_status = self
            .org
            .health
            .as_ref()
            .map(|health| health.status.clone())
            .unwrap_or_else(|| "sem leitura".to_string());
        let health_mode = self
            .org
            .health
            .as_ref()
            .map(|health| health.mode.clone())
            .unwrap_or_else(|| "---".to_string());
        let last_runtime = self
            .org
            .runtime_events
            .first()
            .map(|event| {
                let command = event
                    .command_id
                    .as_deref()
                    .map(short_id)
                    .unwrap_or_else(|| "sem comando".to_string());
                format!(
                    "{} {} {}",
                    command,
                    event.event_type,
                    trim_text(&event.created_at, 19)
                )
            })
            .unwrap_or_else(|| "nenhuma execucao registrada".to_string());
        let last_verification = self
            .org
            .verifications
            .first()
            .map(|verification| {
                let passed = verification
                    .passed
                    .unwrap_or_else(|| verification.status.eq_ignore_ascii_case("passed"));
                format!(
                    "{} {} {}",
                    trim_text(&verification.target, 18),
                    verification.status,
                    if passed { "validado" } else { "falhou" }
                )
            })
            .unwrap_or_else(|| "nenhuma verificacao registrada".to_string());

        let mut log_column = Column::new().spacing(6).push(
            text("LOG ORGANIZACIONAL")
                .size(11)
                .style(Color::from_rgb8(170, 185, 200)),
        );
        for event in self.org.org_events.iter().take(4) {
            log_column = log_column.push(
                text(format!(
                    "{} {} {}",
                    trim_text(&event.created_at, 19),
                    event.event_type,
                    compact_json(&event.payload, 52)
                ))
                .size(11)
                .style(Color::from_rgb8(150, 165, 180)),
            );
        }
        if self.org.org_events.is_empty() {
            log_column = log_column.push(
                text("Nenhum evento organizacional carregado.")
                    .size(11)
                    .style(Color::from_rgb8(150, 165, 180)),
            );
        }

        let console = Column::new()
            .spacing(12)
            .push(
                Row::new()
                    .spacing(14)
                    .align_items(Alignment::Center)
                    .push(
                        text("CENTRO OPERACIONAL")
                            .size(13)
                            .style(Color::from_rgb8(230, 236, 242)),
                    )
                    .push(Space::with_width(Length::Fill))
                    .push(
                        text(
                            self.org
                                .updated_at
                                .as_ref()
                                .map(|value| format!("refresh {}", value))
                                .unwrap_or_else(|| "aguardando refresh".to_string()),
                        )
                        .size(10)
                        .style(Color::from_rgb8(92, 105, 120)),
                    ),
            )
            .push(
                Row::new()
                    .spacing(18)
                    .align_items(Alignment::Start)
                    .push(ops_metric("Daemon", health_status, false))
                    .push(ops_metric("Modo", health_mode, false))
                    .push(ops_metric(
                        "Aprovacoes",
                        self.org.approvals.len().to_string(),
                        !self.org.approvals.is_empty(),
                    ))
                    .push(ops_metric("Runtime", trim_text(&last_runtime, 42), false))
                    .push(ops_metric(
                        "Verificacao",
                        trim_text(&last_verification, 42),
                        false,
                    )),
            )
            .push(log_column);

        container(console)
            .padding([14, 18])
            .width(Length::Fill)
            .style(ops_console_style)
            .into()
    }

    fn activity_panel(&self) -> Element<'_, Message> {
        let last_latency = self
            .last_latency_ms
            .map(|ms| format!("{}ms", ms))
            .unwrap_or_else(|| "sem dado".to_string());
        let pending = self
            .pending_since
            .map(|start| format!("{}s", start.elapsed().as_secs()))
            .unwrap_or_else(|| "nenhum".to_string());

        let visible_activity = self.visible_activity();
        let mut activity_col = Column::new().spacing(12).push(
            text("TRILHA DE ATIVIDADE")
                .size(12)
                .style(Color::from_rgb8(170, 185, 200)),
        );

        for item in visible_activity.iter().rev() {
            let dot_style = match item.level {
                ActivityLevel::Info => info_activity_dot_style,
                ActivityLevel::Success => success_activity_dot_style,
                ActivityLevel::Warning => warning_activity_dot_style,
                ActivityLevel::Error => error_activity_dot_style,
            };
            activity_col = activity_col.push(
                container(
                    Column::new()
                        .spacing(4)
                        .push(
                            Row::new()
                                .spacing(8)
                                .align_items(Alignment::Center)
                                .push(
                                    container(Space::with_width(7))
                                        .width(7)
                                        .height(7)
                                        .style(dot_style),
                                )
                                .push(
                                    text(&item.label)
                                        .size(13)
                                        .style(Color::from_rgb8(230, 236, 242)),
                                )
                                .push(
                                    text(&item.timestamp)
                                        .size(10)
                                        .style(Color::from_rgb8(92, 105, 120)),
                                ),
                        )
                        .push(
                            text(&item.detail)
                                .size(12)
                                .style(Color::from_rgb8(150, 165, 180)),
                        ),
                )
                .padding(10)
                .width(Length::Fill)
                .style(activity_item_style),
            );
        }

        let status_card = container(
            Column::new()
                .spacing(10)
                .push(text("CONTRATO DE EXECUCAO").size(12).style(Color::from_rgb8(170, 185, 200)))
                .push(text("O Nexus nao deve marcar acao como feita sem confirmacao do backend/ledger. Pendencias e falhas ficam visiveis aqui.").size(12).style(Color::from_rgb8(150, 165, 180)))
                .push(Rule::horizontal(1))
                .push(metric_row("Pendente", pending))
                .push(metric_row("Ultima latencia", last_latency))
        )
        .padding(14)
        .width(Length::Fill)
        .style(side_card_style);

        container(
            Column::new()
                .spacing(16)
                .push(status_card)
                .push(self.org_panel())
                .push(activity_col),
        )
        .padding([18, 18])
        .width(310)
        .height(Length::Fill)
        .style(side_panel_style)
        .into()
    }

    fn org_panel(&self) -> Element<'_, Message> {
        let mut panel = Column::new().spacing(10).push(
            text("EMPRESA NEXUS")
                .size(12)
                .style(Color::from_rgb8(170, 185, 200)),
        );

        if let Some(error) = &self.org.error {
            panel = panel.push(
                text(format!("Estado indisponivel: {}", error))
                    .size(12)
                    .style(Color::from_rgb8(255, 200, 90)),
            );
        }

        if let Some(health) = &self.org.health {
            let heartbeat = health
                .heartbeat_age_seconds
                .map(|age| format!("{:.0}s", age))
                .unwrap_or_else(|| "sem heartbeat".to_string());
            panel = panel
                .push(metric_row("Daemon", health.status.clone()))
                .push(metric_row("Modo", health.mode.clone()))
                .push(metric_row("Agentes", health.agents_registered.to_string()))
                .push(metric_row("Tarefas", health.tasks_total.to_string()))
                .push(metric_row("Heartbeat", heartbeat))
                .push(
                    text(&health.detail)
                        .size(11)
                        .style(Color::from_rgb8(150, 165, 180)),
                );
        } else {
            panel = panel.push(
                text("Aguardando leitura do daemon organizacional.")
                    .size(12)
                    .style(Color::from_rgb8(150, 165, 180)),
            );
        }

        if let Some(memory) = &self.org.memory {
            panel = panel
                .push(Rule::horizontal(1))
                .push(metric_row("Memoria", format!("{} eventos", memory.events)))
                .push(metric_row("Decisoes", memory.decisions.to_string()))
                .push(metric_row("Tasks", memory.tasks.to_string()))
                .push(metric_row("Summaries", memory.summaries.to_string()))
                .push(metric_row(
                    "Execucoes",
                    format!("{}/{}", memory.runtime_events, memory.verifications),
                ))
                .push(metric_row("Observer", memory.observations.to_string()))
                .push(metric_row("Ticks", memory.agent_ticks.to_string()));
        }

        panel = panel.push(Rule::horizontal(1)).push(metric_row(
            "Aprovacoes",
            self.org.approvals.len().to_string(),
        ));
        for approval in self.org.approvals.iter().take(2) {
            let proposal_id = approval_proposal_id(approval);
            panel = panel.push(
                Row::new()
                    .spacing(8)
                    .align_items(Alignment::Center)
                    .push(
                        Column::new()
                            .spacing(2)
                            .width(Length::Fill)
                            .push(
                                text(format!(
                                    "{} [{}] {}",
                                    short_id(&proposal_id),
                                    format!("{}/{}", approval.risk, approval.status),
                                    trim_text(&approval.command, 30)
                                ))
                                .size(11)
                                .style(Color::from_rgb8(255, 200, 90)),
                            )
                            .push(
                                text(approval_impact_line(approval))
                                    .size(10)
                                    .style(Color::from_rgb8(150, 165, 180)),
                            ),
                    )
                    .push(
                        button(text("ver").size(11))
                            .on_press(Message::SelectPendingApproval(proposal_id)),
                    ),
            );
        }

        if let Some(selected) = self.selected_pending_approval() {
            panel = panel.push(self.approval_detail_card(
                "PENDENTE SELECIONADO",
                selected,
                Some(Message::ApproveSelected),
                "aprovar uma vez",
            ));
        }

        if !self.org.approved_commands.is_empty() {
            panel = panel.push(Rule::horizontal(1)).push(metric_row(
                "Executaveis",
                self.org.approved_commands.len().to_string(),
            ));
            for approval in self.org.approved_commands.iter().take(2) {
                let proposal_id = approval_proposal_id(approval);
                panel = panel.push(
                    Row::new()
                        .spacing(8)
                        .align_items(Alignment::Center)
                        .push(
                            text(format!(
                                "{} {}",
                                short_id(&proposal_id),
                                trim_text(&approval.command, 34)
                            ))
                            .size(11)
                            .style(Color::from_rgb8(112, 224, 180))
                            .width(Length::Fill),
                        )
                        .push(
                            button(text("ver").size(11))
                                .on_press(Message::SelectApprovedCommand(proposal_id)),
                        ),
                );
            }
        }

        if let Some(selected) = self.selected_approved_command() {
            panel = panel.push(self.approval_detail_card(
                "APROVADO SELECIONADO",
                selected,
                Some(Message::ExecuteSelected),
                "executar",
            ));
        }

        if !self.org.agent_ticks.is_empty() {
            panel = panel.push(Rule::horizontal(1)).push(
                text("AGENTES ATIVOS")
                    .size(11)
                    .style(Color::from_rgb8(170, 185, 200)),
            );
            for tick in self.org.agent_ticks.iter().take(4) {
                panel = panel.push(
                    text(format!(
                        "{}: {} - {} ({})",
                        tick.agent_id,
                        tick.status,
                        trim_text(&tick.summary, 32),
                        tick.created_at
                    ))
                    .size(11)
                    .style(Color::from_rgb8(150, 165, 180)),
                );
            }
        }

        if let Some(event) = self.org.runtime_events.first() {
            let command = event
                .command_id
                .as_deref()
                .map(short_id)
                .unwrap_or_else(|| "sem comando".to_string());
            panel = panel.push(Rule::horizontal(1)).push(
                text(format!(
                    "Runtime {}: {} - {} ({})",
                    command,
                    event.event_type,
                    trim_text(&event.message, 42),
                    event.created_at
                ))
                .size(11)
                .style(Color::from_rgb8(150, 165, 180)),
            );
        }

        if let Some(verification) = self.org.verifications.first() {
            let passed = verification
                .passed
                .unwrap_or_else(|| verification.status.eq_ignore_ascii_case("passed"));
            let color = if passed {
                Color::from_rgb8(112, 224, 180)
            } else {
                Color::from_rgb8(255, 95, 110)
            };
            panel = panel.push(
                text(format!(
                    "Verify {}: {} {} - {} ({})",
                    verification.target,
                    verification.status,
                    if passed { "ok" } else { "falhou" },
                    trim_text(&verification_evidence_line(verification), 32),
                    verification.created_at
                ))
                .size(11)
                .style(color),
            );
        }

        if let Some(updated_at) = &self.org.updated_at {
            panel = panel.push(
                text(format!("Atualizado {}", updated_at))
                    .size(10)
                    .style(Color::from_rgb8(92, 105, 120)),
            );
        }

        container(panel)
            .padding(14)
            .width(Length::Fill)
            .style(side_card_style)
            .into()
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
}

fn metric_row<'a>(label: &'static str, value: String) -> Row<'a, Message> {
    Row::new()
        .align_items(Alignment::Center)
        .push(text(label).size(12).style(Color::from_rgb8(132, 145, 160)))
        .push(Space::with_width(Length::Fill))
        .push(text(value).size(12).style(Color::from_rgb8(230, 236, 242)))
}

fn ops_metric<'a>(label: &'static str, value: String, alert: bool) -> Column<'a, Message> {
    let value_color = if alert {
        Color::from_rgb8(255, 200, 90)
    } else {
        Color::from_rgb8(230, 236, 242)
    };
    Column::new()
        .spacing(3)
        .width(Length::FillPortion(1))
        .push(text(label).size(10).style(Color::from_rgb8(132, 145, 160)))
        .push(text(value).size(12).style(value_color))
}

fn telemetry_item<'a>(label: &'static str, val: String, alert: bool) -> Column<'a, Message> {
    let val_color = if alert {
        Color::from_rgb8(255, 60, 80)
    } else {
        Color::from_rgb8(255, 255, 255)
    };
    Column::new()
        .push(text(label).size(10).style(Color::from_rgb8(132, 145, 160)))
        .push(text(val).size(18).style(val_color))
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

fn hud_top_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(13, 18, 24).into()),
        ..Default::default()
    }
}
fn bottom_bar_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(15, 20, 27).into()),
        border: Border {
            color: Color::from_rgb8(38, 48, 60),
            width: 1.0,
            radius: 0.0.into(),
        },
        ..Default::default()
    }
}
fn input_field_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(22, 28, 36).into()),
        border: Border {
            color: Color::from_rgb8(58, 70, 84),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn transmit_btn_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(28, 115, 184).into()),
        border: Border {
            color: Color::from_rgb8(86, 160, 220),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn nexus_bubble_modern(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(24, 32, 42).into()),
        border: Border {
            color: Color::from_rgb8(64, 105, 140),
            width: 1.0,
            radius: [8.0, 8.0, 8.0, 2.0].into(),
        },
        ..Default::default()
    }
}
fn operator_bubble_modern(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(38, 34, 27).into()),
        border: Border {
            color: Color::from_rgb8(180, 140, 64),
            width: 1.0,
            radius: [8.0, 8.0, 2.0, 8.0].into(),
        },
        ..Default::default()
    }
}
fn error_bubble_modern(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(48, 25, 29).into()),
        border: Border {
            color: Color::from_rgb8(255, 95, 110),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn progress_bubble_modern(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(30, 39, 50).into()),
        border: Border {
            color: Color::from_rgb8(86, 160, 220),
            width: 1.0,
            radius: [8.0, 8.0, 8.0, 2.0].into(),
        },
        ..Default::default()
    }
}
fn side_panel_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(16, 21, 28).into()),
        border: Border {
            color: Color::from_rgb8(38, 48, 60),
            width: 1.0,
            radius: 0.0.into(),
        },
        ..Default::default()
    }
}
fn side_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(22, 28, 36).into()),
        border: Border {
            color: Color::from_rgb8(48, 60, 74),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn ops_console_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(18, 24, 32).into()),
        border: Border {
            color: Color::from_rgb8(48, 60, 74),
            width: 1.0,
            radius: 0.0.into(),
        },
        ..Default::default()
    }
}
fn activity_item_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(18, 24, 32).into()),
        border: Border {
            color: Color::from_rgb8(34, 45, 58),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}
fn info_activity_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(130, 180, 235).into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
fn success_activity_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(112, 224, 180).into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
fn warning_activity_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(255, 200, 90).into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
fn error_activity_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(255, 95, 110).into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
fn success_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(0, 255, 136).into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
fn error_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb8(255, 60, 80).into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
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
    let health = run_org_json::<OrgHealth>(&["health"]).await?;
    let memory = run_org_json::<OrgMemoryStatus>(&["memory-status"]).await?;
    let agent_ticks = run_org_json::<Vec<AgentTick>>(&["agent-ticks", "--limit", "6"]).await?;
    let approvals =
        run_org_json::<Vec<ApprovalItem>>(&["approvals", "--status", "pending_approval"]).await?;
    let runtime_events =
        run_org_json::<Vec<RuntimeEvent>>(&["runtime-events", "--limit", "3"]).await?;
    let verifications =
        run_org_json::<Vec<VerificationItem>>(&["verifications", "--limit", "3"]).await?;
    let org_events = run_org_json::<Vec<OrgEvent>>(&["memory-events", "--limit", "6"]).await?;
    let approved_commands =
        run_org_json::<Vec<ApprovalItem>>(&["approvals", "--status", "approved"]).await?;

    Ok(OrgDashboard {
        health: Some(health),
        memory: Some(memory),
        agent_ticks,
        approvals,
        approved_commands,
        runtime_events,
        verifications,
        org_events,
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
