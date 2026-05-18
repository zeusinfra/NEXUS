#![allow(dead_code)]

use iced::widget::{
    button, container, scrollable, svg, text, text_input, toggler, tooltip, Column, Row, Rule,
    Space, Svg, Toggler, Tooltip,
};
use iced::{
    theme, Alignment, Application, Border, Color, Command, Element, Event, Length, Settings,
    Subscription, Theme,
};
use reqwest::Client;
use rodio::{Decoder, OutputStream, Sink};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use std::io::Cursor;
use std::path::PathBuf;
use std::time::{Duration, Instant};
use sysinfo::System;
use tokio::process::Command as TokioCommand;

mod websocket;

mod design {
    use iced::Color;

    pub const BACKGROUND: Color = Color::from_rgb(0.020, 0.031, 0.086);
    pub const SURFACE: Color = Color::from_rgb(0.030, 0.041, 0.070);
    pub const SURFACE_HIGH: Color = Color::from_rgb(0.046, 0.062, 0.092);
    pub const STROKE: Color = Color::from_rgb(0.100, 0.135, 0.180);
    pub const TEXT_PRIMARY: Color = Color::from_rgb(0.930, 0.950, 0.970);
    pub const TEXT_SECONDARY: Color = Color::from_rgb(0.650, 0.700, 0.760);
    pub const TEXT_MUTED: Color = Color::from_rgb(0.430, 0.480, 0.560);
    pub const ACCENT: Color = Color::from_rgb(0.100, 0.620, 0.700);
    pub const ACCENT_SOFT: Color = Color::from_rgb(0.035, 0.180, 0.225);
    pub const CYAN: Color = Color::from_rgb(0.220, 0.860, 0.930);
    pub const PETROL: Color = Color::from_rgb(0.030, 0.170, 0.220);
    pub const SUCCESS: Color = Color::from_rgb(0.260, 0.820, 0.580);
    pub const WARNING: Color = Color::from_rgb(0.900, 0.670, 0.300);
    pub const DANGER: Color = Color::from_rgb(0.900, 0.330, 0.390);
}

pub fn main() -> iced::Result {
    NexusApp::run(Settings {
        window: iced::window::Settings {
            size: iced::Size::new(1440.0, 900.0),
            min_size: Some(iced::Size::new(360.0, 560.0)),
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
    viewport_width: f32,
    viewport_height: f32,
    copied_feedback: Option<String>,
    product: Option<ProductStatus>,
    product_error: Option<String>,
    engineering_mode: bool,
    active_section: SidebarSection,
    pending_approval: Option<(String, String, websocket::RiskLevel)>,
}

#[derive(Clone, Debug)]
struct ChatMessage {
    role: String,
    content: String,
    timestamp: String,
    feedback: Option<ChatFeedback>,
}

#[derive(Clone, Debug, Deserialize)]
struct ChatFeedback {
    intent_label: String,
    status_label: String,
    confidence_label: String,
    user_hint: String,
    #[serde(default)]
    evidence: Vec<String>,
    #[serde(default)]
    next_steps: Vec<String>,
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

#[derive(Clone, Copy, Debug)]
enum NexusIcon {
    Message,
    Task,
    Settings,
    Document,
    List,
    Circle,
    ArrowUpRight,
    Send,
    Mic,
    Paperclip,
    ChevronDown,
    ChevronRight,
    Sparkle,
    Lock,
    Check,
}

impl NexusIcon {
    fn svg(self) -> &'static str {
        match self {
            Self::Message => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 6.8A3.8 3.8 0 0 1 8.8 3h6.4A3.8 3.8 0 0 1 19 6.8v5.4a3.8 3.8 0 0 1-3.8 3.8h-4.7L6 20v-4.2a3.8 3.8 0 0 1-1-2.6Z"/></svg>"#
            }
            Self::Task => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="18" rx="3"/><path d="m9 12 2 2 4-5"/><path d="M9 17h6"/><path d="M9 7h6"/></svg>"#
            }
            Self::Settings => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v2"/><path d="M12 19v2"/><path d="m4.9 4.9 1.4 1.4"/><path d="m17.7 17.7 1.4 1.4"/><path d="M3 12h2"/><path d="M19 12h2"/><path d="m4.9 19.1 1.4-1.4"/><path d="m17.7 6.3 1.4-1.4"/><circle cx="12" cy="12" r="4"/></svg>"#
            }
            Self::Document => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h7l4 4v14H7z"/><path d="M14 3v5h5"/><path d="M10 12h5"/><path d="M10 16h5"/><path d="M10 8h1"/></svg>"#
            }
            Self::List => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6h11"/><path d="M9 12h11"/><path d="M9 18h11"/><path d="M4 6h.01"/><path d="M4 12h.01"/><path d="M4 18h.01"/></svg>"#
            }
            Self::Circle => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="6.5"/></svg>"#
            }
            Self::ArrowUpRight => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7"/><path d="M9 7h8v8"/></svg>"#
            }
            Self::Send => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="m6 11 6-6 6 6"/></svg>"#
            }
            Self::Mic => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>"#
            }
            Self::Paperclip => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m21 11-8.8 8.8a5 5 0 0 1-7.1-7.1L14 3.8a3.2 3.2 0 0 1 4.5 4.5l-8.7 8.7a1.5 1.5 0 0 1-2.1-2.1L16 6.6"/></svg>"#
            }
            Self::ChevronDown => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 10 5 5 5-5"/></svg>"#
            }
            Self::ChevronRight => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>"#
            }
            Self::Sparkle => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 14 9l6 3-6 3-2 6-2-6-6-3 6-3z"/></svg>"#
            }
            Self::Lock => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="10" width="14" height="10" rx="2.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>"#
            }
            Self::Check => {
                r#"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="m5 13 4 4L19 7"/></svg>"#
            }
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Breakpoint {
    MobileSmall,
    MobileLarge,
    Tablet,
    Laptop,
    Desktop,
    Ultrawide,
}

impl Breakpoint {
    fn from_width(width: f32) -> Self {
        match width {
            width if width <= 480.0 => Self::MobileSmall,
            width if width <= 640.0 => Self::MobileLarge,
            width if width <= 1024.0 => Self::Tablet,
            width if width <= 1366.0 => Self::Laptop,
            width if width <= 1920.0 => Self::Desktop,
            _ => Self::Ultrawide,
        }
    }

    fn is_mobile(self) -> bool {
        matches!(self, Self::MobileSmall | Self::MobileLarge)
    }

    fn is_tablet_or_smaller(self) -> bool {
        matches!(self, Self::MobileSmall | Self::MobileLarge | Self::Tablet)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum DensityMode {
    Compact,
    Balanced,
    Expanded,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum SidebarSection {
    Overview,
    Conversation,
    Missions,
    Swarm,
    Executions,
    Approvals,
    Incidents,
    Observer,
    Telemetry,
    Memory,
    Settings,
}

impl SidebarSection {
    fn label(self) -> &'static str {
        match self {
            Self::Overview => "Visão Geral",
            Self::Conversation => "Conversas",
            Self::Missions => "Tarefas",
            Self::Swarm => "Swarm",
            Self::Executions => "Execuções",
            Self::Approvals => "Aprovações",
            Self::Incidents => "Incidentes",
            Self::Observer => "Observador",
            Self::Telemetry => "Telemetry",
            Self::Memory => "Memória",
            Self::Settings => "Configurações",
        }
    }

    fn title(self) -> &'static str {
        match self {
            Self::Overview => "Visão Geral",
            Self::Conversation => "Conversas",
            Self::Missions => "Tarefas",
            Self::Swarm => "Swarm",
            Self::Executions => "Execuções",
            Self::Approvals => "Aprovações",
            Self::Incidents => "Incidentes",
            Self::Observer => "Observer",
            Self::Telemetry => "Telemetry",
            Self::Memory => "Memória",
            Self::Settings => "Configurações",
        }
    }

    fn subtitle(self) -> &'static str {
        match self {
            Self::Overview => "Centro de comando operacional do NEXUS",
            Self::Conversation => "Canal direto com o agente cognitivo",
            Self::Missions => "Objetivos, progresso e próximos passos",
            Self::Swarm => "Coordenação dos agentes cognitivos",
            Self::Executions => "Runtime, evidências e resultados",
            Self::Approvals => "Comandos sensíveis aguardando decisão",
            Self::Incidents => "Falhas e alertas operacionais",
            Self::Observer => "Contexto vivo do Linux",
            Self::Telemetry => "Carga cognitiva, runtime e memória",
            Self::Memory => "Registros e aprendizados persistidos",
            Self::Settings => "Instalação, modelos e modo de uso",
        }
    }
}

#[derive(Clone, Debug, Default)]
struct OrgDashboard {
    health: Option<OrgHealth>,
    memory: Option<OrgMemoryStatus>,
    agent_ticks: Vec<AgentTick>,
    approvals: Vec<ApprovalItem>,
    approved_commands: Vec<ApprovalItem>,
    commands: Vec<CommandItem>,
    runtime_events: Vec<RuntimeEvent>,
    verifications: Vec<VerificationItem>,
    org_events: Vec<OrgEvent>,
    swarm: Option<SwarmStatus>,
    incidents: Vec<IncidentItem>,
    observations: Vec<ObservationItem>,
    memory_entries: Vec<MemoryEntry>,
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
    #[serde(default)]
    agents: i64,
    #[serde(default)]
    commands: i64,
    #[serde(default)]
    incidents: i64,
    #[serde(default)]
    approvals: i64,
    #[serde(default)]
    memory_entries: i64,
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
    stream: Option<String>,
    #[serde(default)]
    payload: serde_json::Value,
    #[serde(default)]
    message: String,
    created_at: String,
}

#[derive(Clone, Debug, Deserialize)]
struct CommandItem {
    command_id: String,
    agent_id: Option<String>,
    task_id: Option<String>,
    proposal_id: Option<String>,
    command: String,
    cwd: String,
    status: String,
    pid: Option<i64>,
    exit_code: Option<i64>,
    duration_ms: Option<i64>,
    stdout_path: Option<String>,
    stderr_path: Option<String>,
    evidence_path: Option<String>,
    risk_level: String,
    created_at: String,
    finished_at: Option<String>,
    #[serde(default)]
    metadata: serde_json::Value,
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
    #[serde(default)]
    risk_level: String,
    #[serde(default)]
    success_criteria: Vec<String>,
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
    updated_at: Option<String>,
    #[serde(default)]
    metadata: serde_json::Value,
}

#[allow(dead_code)]
#[derive(Clone, Debug, Deserialize)]
struct IncidentItem {
    id: Option<String>,
    severity: String,
    module: String,
    message: String,
    created_at: String,
    agent_id: Option<String>,
    task_id: Option<String>,
    command_id: Option<String>,
    risk_level: Option<String>,
    #[serde(default)]
    metadata: serde_json::Value,
}

#[allow(dead_code)]
#[derive(Clone, Debug, Deserialize)]
struct ObservationItem {
    mode: String,
    confidence: f32,
    active_window: Option<String>,
    #[serde(default)]
    system: serde_json::Value,
    #[serde(default)]
    processes: Vec<serde_json::Value>,
    #[serde(default)]
    triggers: Vec<serde_json::Value>,
    created_at: String,
}

#[allow(dead_code)]
#[derive(Clone, Debug, Deserialize)]
struct MemoryEntry {
    scope: String,
    kind: String,
    content: String,
    source: String,
    created_at: String,
}

#[derive(Clone, Debug, Deserialize)]
struct ProductStatus {
    autonomy_level: String,
    daemon: ProductDaemonStatus,
    models: ProductModelsStatus,
    paths: ProductPathsStatus,
}

#[derive(Clone, Debug, Deserialize)]
struct ProductDaemonStatus {
    status: String,
    detail: String,
    mode: String,
    agents: usize,
    tasks: usize,
    pid: Option<i64>,
    pid_alive: bool,
    heartbeat_age_s: Option<f64>,
}

#[derive(Clone, Debug, Deserialize)]
struct ProductModelsStatus {
    mode: String,
    local: ProductLocalModelStatus,
    cloud: ProductCloudStatus,
}

#[derive(Clone, Debug, Deserialize)]
struct ProductLocalModelStatus {
    ready: bool,
    selected_model: Option<String>,
    model_count: usize,
    endpoint: String,
    api_ok: bool,
    binary_found: bool,
}

#[derive(Clone, Debug, Deserialize)]
struct ProductCloudStatus {
    ready: bool,
    provider: String,
    model: String,
    api_key_env: String,
}

#[derive(Clone, Debug, Deserialize)]
struct ProductPathsStatus {
    config: String,
    data_dir: String,
    log_dir: String,
    project_root: String,
}

#[derive(Clone, Debug, Deserialize)]
struct OrgDashboardPayload {
    health: OrgHealth,
    memory_status: OrgMemoryStatus,
    #[serde(default)]
    agents: Vec<SwarmAgent>,
    agent_ticks: Vec<AgentTick>,
    approvals: Vec<ApprovalItem>,
    approved_commands: Vec<ApprovalItem>,
    #[serde(default)]
    commands: Vec<CommandItem>,
    runtime_events: Vec<RuntimeEvent>,
    verifications: Vec<VerificationItem>,
    org_events: Vec<OrgEvent>,
    swarm: Option<SwarmStatus>,
    incidents: Vec<IncidentItem>,
    #[serde(default)]
    observations: Vec<ObservationItem>,
    #[serde(default)]
    memory_entries: Vec<MemoryEntry>,
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
    ProductStatusLoaded(Result<ProductStatus, String>),
    ToggleEngineeringMode,
    SelectSection(SidebarSection),
    PromptSelected(&'static str),
    CopyCurrentCommand,
    CopyRuntimeLogs,
    EventOccurred(Event),
    Tick,
    BackendEventReceived(websocket::Event),
    ReplyApproval(String, bool), // (command_id, is_approve)
    ApprovalReplied(Result<String, String>),
}

const SCROLLABLE_ID: &str = "chat_scroll";
const HEALTH_CHECK_INTERVAL: u32 = 5;
const WINDOW_INITIAL_WIDTH: f32 = 1440.0;
const WINDOW_INITIAL_HEIGHT: f32 = 900.0;
const BG: Color = design::BACKGROUND;
const SURFACE: Color = design::SURFACE;
const SURFACE_HIGH: Color = design::SURFACE_HIGH;
const STROKE: Color = design::STROKE;
const TEXT_PRIMARY: Color = design::TEXT_PRIMARY;
const TEXT_SECONDARY: Color = design::TEXT_SECONDARY;
const TEXT_MUTED: Color = design::TEXT_MUTED;
const ACCENT: Color = design::ACCENT;
const ACCENT_SOFT: Color = design::ACCENT_SOFT;
const CYAN: Color = design::CYAN;
const PETROL: Color = design::PETROL;
const PURPLE: Color = Color::from_rgb(0.58, 0.36, 0.94);
const SUCCESS: Color = design::SUCCESS;
const WARNING: Color = design::WARNING;
const DANGER: Color = design::DANGER;

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
                    content: "Olá! Eu sou o NEXUS, seu assistente inteligente.\nEm que posso ajudar você hoje?".to_string(),
                    timestamp: current_time(),
                    feedback: None,
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
                viewport_width: WINDOW_INITIAL_WIDTH,
                viewport_height: WINDOW_INITIAL_HEIGHT,
                copied_feedback: None,
                product: None,
                product_error: None,
                engineering_mode: false,
                active_section: SidebarSection::Conversation,
                pending_approval: None,
            },
            Command::batch(vec![
                Command::perform(check_status(), Message::StatusChecked),
                Command::perform(load_org_dashboard(), Message::OrgDashboardLoaded),
                Command::perform(load_product_status(), Message::ProductStatusLoaded),
            ]),
        )
    }

    fn title(&self) -> String {
        String::from("NEXUS Cognitive OS — Operations Center")
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
                        Command::perform(load_product_status(), Message::ProductStatusLoaded),
                    ]);
                }
                Command::none()
            }
            Message::EventOccurred(event) => {
                if let Event::Window(_, iced::window::Event::Resized { width, height }) = event {
                    self.viewport_width = width as f32;
                    self.viewport_height = height as f32;
                }
                Command::none()
            }
            Message::InputChanged(val) => {
                self.input_value = val;
                Command::none()
            }
            Message::PromptSelected(prompt) => {
                self.input_value = prompt.to_string();
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
                    feedback: None,
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
                    feedback: response.feedback.clone(),
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
                    feedback: None,
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
            Message::ProductStatusLoaded(Ok(status)) => {
                let previous = self.product.as_ref().map(|item| item.daemon.status.clone());
                let current = status.daemon.status.clone();
                self.product = Some(status);
                self.product_error = None;
                if previous.as_deref() != Some(current.as_str()) {
                    self.push_activity(
                        "Produto Linux",
                        &format!("Daemon systemd reportou estado {}.", current),
                        if current == "online" {
                            ActivityLevel::Success
                        } else {
                            ActivityLevel::Warning
                        },
                    );
                }
                Command::none()
            }
            Message::ProductStatusLoaded(Err(error)) => {
                if self.product_error.as_deref() != Some(error.as_str()) {
                    self.push_activity(
                        "Produto Linux",
                        &format!("Nao foi possivel ler nexus status: {}", error),
                        ActivityLevel::Warning,
                    );
                }
                self.product_error = Some(error);
                Command::none()
            }
            Message::ToggleEngineeringMode => {
                self.engineering_mode = !self.engineering_mode;
                self.push_activity(
                    "Modo de interface",
                    if self.engineering_mode {
                        "Modo engenharia ativado: detalhes tecnicos ficam visiveis."
                    } else {
                        "Modo publico ativado: foco em clareza operacional."
                    },
                    ActivityLevel::Info,
                );
                Command::none()
            }
            Message::SelectSection(section) => {
                self.active_section = section;
                self.push_activity(
                    "Navegacao",
                    &format!("Abrindo painel {}.", section.label()),
                    ActivityLevel::Info,
                );
                Command::none()
            }
            Message::CopyCurrentCommand => {
                if let Some(command) = self.org.commands.first() {
                    self.copied_feedback =
                        Some(format!("command {} copied", short_id(&command.command_id)));
                    return iced::clipboard::write(command.command.clone());
                }
                Command::none()
            }
            Message::CopyRuntimeLogs => {
                let logs = self.runtime_log_text();
                if logs.trim().is_empty() {
                    return Command::none();
                }
                self.copied_feedback = Some("runtime evidence copied".to_string());
                iced::clipboard::write(logs)
            }
            Message::ReplyApproval(command_id, approve) => {
                self.pending_approval = None;
                self.push_activity(
                    "Aprovacao",
                    &format!(
                        "Resposta enviada: {}",
                        if approve { "Approve" } else { "Deny" }
                    ),
                    ActivityLevel::Info,
                );
                Command::perform(
                    reply_approval(command_id, approve),
                    Message::ApprovalReplied,
                )
            }
            Message::ApprovalReplied(Ok(res)) => {
                self.push_activity("Aprovacao Confirmada", &res, ActivityLevel::Success);
                Command::none()
            }
            Message::ApprovalReplied(Err(e)) => {
                self.push_activity("Falha na Aprovacao", &e, ActivityLevel::Error);
                Command::none()
            }
            Message::BackendEventReceived(event) => {
                match event {
                    websocket::Event::Connected => {
                        self.status = "ONLINE".to_string();
                        self.push_activity(
                            "WebSocket",
                            "Conectado ao NEXUS Core",
                            ActivityLevel::Success,
                        );
                    }
                    websocket::Event::Disconnected => {
                        self.status = "OFFLINE".to_string();
                        self.push_activity(
                            "WebSocket",
                            "Desconectado do NEXUS Core",
                            ActivityLevel::Error,
                        );
                    }
                    websocket::Event::Error(e) => {
                        self.push_activity("WebSocket Erro", &e, ActivityLevel::Error);
                    }
                    websocket::Event::MessageReceived(sys_event) => {
                        match sys_event {
                            websocket::SystemEvent::ApprovalRequested {
                                command_id,
                                command,
                                risk,
                            } => {
                                self.pending_approval = Some((command_id, command, risk));
                            }
                            websocket::SystemEvent::CommandStarted {
                                command_id: _,
                                command,
                            } => {
                                self.push_activity(
                                    "Comando",
                                    &format!("Iniciando: {}", command),
                                    ActivityLevel::Warning,
                                );
                            }
                            websocket::SystemEvent::CommandOutput {
                                command_id: _,
                                chunk,
                                is_error: _,
                            } => {
                                if let Some(last_msg) = self.messages.last_mut() {
                                    if last_msg.role == "TERMINAL" {
                                        last_msg.content.push_str(&chunk);
                                    } else {
                                        self.messages.push(ChatMessage {
                                            role: "TERMINAL".to_string(),
                                            content: chunk,
                                            timestamp: current_time(),
                                            feedback: None,
                                        });
                                    }
                                } else {
                                    self.messages.push(ChatMessage {
                                        role: "TERMINAL".to_string(),
                                        content: chunk,
                                        timestamp: current_time(),
                                        feedback: None,
                                    });
                                }
                                self.is_thinking = false;
                                return scrollable::snap_to(
                                    scrollable::Id::new(SCROLLABLE_ID),
                                    scrollable::RelativeOffset::END,
                                );
                            }
                            websocket::SystemEvent::CommandFinished {
                                command_id: _,
                                exit_code,
                            } => {
                                let status = if exit_code == 0 {
                                    ActivityLevel::Success
                                } else {
                                    ActivityLevel::Error
                                };
                                self.push_activity(
                                    "Comando Concluido",
                                    &format!("Exit code: {}", exit_code),
                                    status,
                                );
                            }
                            websocket::SystemEvent::PatchPreview { path, diff: _ } => {
                                self.push_activity(
                                    "Patch",
                                    &format!("Preparando alteracao: {}", path),
                                    ActivityLevel::Info,
                                );
                            }
                            websocket::SystemEvent::RollbackCreated { backup_path } => {
                                self.push_activity(
                                    "Backup",
                                    &format!("Salvo em: {}", backup_path),
                                    ActivityLevel::Success,
                                );
                            }
                            websocket::SystemEvent::FilePatched { path } => {
                                self.push_activity(
                                    "Arquivo Alterado",
                                    &path,
                                    ActivityLevel::Warning,
                                );
                            }
                            websocket::SystemEvent::FileChanged { path } => {
                                self.push_activity(
                                    "Filesystem",
                                    &format!("Arquivo modificado: {}", path),
                                    ActivityLevel::Info,
                                );
                            }
                            websocket::SystemEvent::MessageStreamChunk { id: _, chunk } => {
                                if let Some(last_msg) = self.messages.last_mut() {
                                    if last_msg.role == "NEXUS" {
                                        last_msg.content.push_str(&chunk);
                                    } else {
                                        self.messages.push(ChatMessage {
                                            role: "NEXUS".to_string(),
                                            content: chunk,
                                            timestamp: current_time(),
                                            feedback: None,
                                        });
                                    }
                                } else {
                                    self.messages.push(ChatMessage {
                                        role: "NEXUS".to_string(),
                                        content: chunk,
                                        timestamp: current_time(),
                                        feedback: None,
                                    });
                                }
                                self.is_thinking = false;
                                return scrollable::snap_to(
                                    scrollable::Id::new(SCROLLABLE_ID),
                                    scrollable::RelativeOffset::END,
                                );
                            }
                            websocket::SystemEvent::TaskCompleted { task_id } => {
                                self.push_activity(
                                    "Tarefa Concluida",
                                    &task_id,
                                    ActivityLevel::Success,
                                );
                            }
                            websocket::SystemEvent::TaskStateChanged {
                                task_id: _,
                                state,
                                message,
                            } => {
                                self.push_activity(
                                    "Task State",
                                    &format!("{}: {}", state, message),
                                    ActivityLevel::Info,
                                );
                            }
                            websocket::SystemEvent::EvidenceGenerated {
                                task_id: _,
                                evidence_type,
                                content,
                                diff,
                                backup_path,
                            } => {
                                let mut display_text =
                                    format!("Evidência Registrada ({}):\n", evidence_type);
                                if let Some(d) = diff {
                                    display_text.push_str(&format!("```diff\n{}\n```", d));
                                }
                                if let Some(c) = content {
                                    display_text.push_str(&format!("```\n{}\n```", c));
                                }

                                let msg = ChatMessage {
                                    role: "EVIDENCE".to_string(),
                                    content: display_text,
                                    timestamp: current_time(),
                                    feedback: None,
                                };
                                self.messages.push(msg);

                                // Se tivermos um backup path, vamos injetar um botão de rollback, isso pode ser feito via widget.
                                // Para simplificar o estado, se precisarmos de rollback renderizamos.
                                if let Some(path) = backup_path {
                                    self.push_activity(
                                        "Rollback Disponível",
                                        &path,
                                        ActivityLevel::Warning,
                                    );
                                }

                                return scrollable::snap_to(
                                    scrollable::Id::new(SCROLLABLE_ID),
                                    scrollable::RelativeOffset::END,
                                );
                            }
                            _ => {}
                        }
                    }
                }
                Command::none()
            }
        }
    }

    fn subscription(&self) -> Subscription<Message> {
        Subscription::batch(vec![
            iced::time::every(Duration::from_millis(1000)).map(|_| Message::Tick),
            iced::event::listen().map(Message::EventOccurred),
            websocket::connect().map(Message::BackendEventReceived),
        ])
    }

    fn view(&self) -> Element<'_, Message> {
        let breakpoint = self.breakpoint();
        let uptime = self.session_start.elapsed();
        let uptime_str = format!(
            "uptime {}m {}s",
            uptime.as_secs() / 60,
            uptime.as_secs() % 60
        );

        let is_online = self.status == "ONLINE";
        let status_pill = container(
            Row::new()
                .spacing(8)
                .align_items(Alignment::Center)
                .push(container(Space::new(8, 8)).style(if is_online {
                    success_dot_style
                } else {
                    danger_dot_style
                }))
                .push(text(&self.status).size(12).style(TEXT_PRIMARY)),
        )
        .padding([4, 12])
        .style(status_pill_style);

        let model_label = self
            .product
            .as_ref()
            .and_then(|status| status.models.local.selected_model.as_deref())
            .unwrap_or("local pending")
            .to_string();
        let local_ready = self
            .product
            .as_ref()
            .map(|status| status.models.local.ready)
            .unwrap_or(false);
        let cloud_ready = self
            .product
            .as_ref()
            .map(|status| status.models.cloud.ready)
            .unwrap_or(false);
        let cloud_label = self
            .product
            .as_ref()
            .map(|status| status.models.cloud.model.clone())
            .unwrap_or_else(|| "GPT-5.5".to_string());
        let daemon_label = self
            .product
            .as_ref()
            .map(|status| friendly_status(&status.daemon.status))
            .unwrap_or_else(|| "carregando".to_string());
        let mode_label = self
            .product
            .as_ref()
            .map(|status| status.models.mode.clone())
            .unwrap_or_else(|| "Híbrido".to_string());

        let top_cards = Row::new()
            .spacing(10)
            .align_items(Alignment::Center)
            .push(header_status_card(
                if is_online { "Online" } else { "Offline" },
                "Sistema operacional".to_string(),
                daemon_label,
                if is_online { SUCCESS } else { DANGER },
            ))
            .push(header_status_card(
                "Local AI",
                trim_text(&model_label, 18),
                if local_ready {
                    "Online".to_string()
                } else {
                    "Pendente".to_string()
                },
                CYAN,
            ))
            .push(header_status_card(
                "Cloud AI",
                trim_text(&cloud_label, 16),
                if cloud_ready {
                    "Online".to_string()
                } else {
                    "Aguardando".to_string()
                },
                PURPLE,
            ))
            .push(header_status_card(
                "Modo",
                trim_text(&mode_label, 14),
                if self.engineering_mode {
                    "Engenharia".to_string()
                } else {
                    "Operador".to_string()
                },
                PURPLE,
            ));

        let title_block = Column::new()
            .spacing(4)
            .push(
                text(self.active_section.title())
                    .size(if breakpoint.is_mobile() { 18 } else { 24 })
                    .style(TEXT_PRIMARY),
            )
            .push(
                text(format!(
                    "{} · {}",
                    self.active_section.subtitle(),
                    uptime_str
                ))
                .size(11)
                .style(TEXT_MUTED),
            );

        let header_content: Element<'_, Message> = if breakpoint.is_mobile() {
            Column::new()
                .spacing(12)
                .push(
                    Row::new()
                        .align_items(Alignment::Center)
                        .push(title_block)
                        .push(Space::with_width(Length::Fill))
                        .push(status_pill),
                )
                .push(
                    scrollable(top_cards)
                        .direction(scrollable::Direction::Horizontal(
                            scrollable::Properties::new().width(4),
                        ))
                        .height(Length::Fixed(58.0)),
                )
                .into()
        } else {
            Row::new()
                .spacing(16)
                .align_items(Alignment::Center)
                .push(title_block)
                .push(Space::with_width(Length::Fill))
                .push(top_cards)
                .push(status_pill)
                .into()
        };

        let _header = container(header_content)
            .padding(self.outer_padding())
            .style(header_style);

        let footer_content: Element<'_, Message> = if breakpoint.is_mobile() {
            Column::new()
                .spacing(6)
                .push(text("HUD").size(11).style(ACCENT))
                .push(text(self.hud_line()).size(11).style(TEXT_SECONDARY))
                .push(
                    text(format!(
                        "ORG POLL {}s · {}",
                        HEALTH_CHECK_INTERVAL,
                        self.org
                            .updated_at
                            .as_deref()
                            .unwrap_or("LAST EVENT pending")
                    ))
                    .size(10)
                    .style(TEXT_MUTED),
                )
                .into()
        } else {
            Row::new()
                .spacing(16)
                .align_items(Alignment::Center)
                .push(text("HUD:").size(12).style(ACCENT).width(48))
                .push(text(self.hud_line()).size(12).style(TEXT_SECONDARY))
                .push(Space::with_width(Length::Fill))
                .push(
                    text(format!("ORG POLL {}s", HEALTH_CHECK_INTERVAL))
                        .size(11)
                        .style(TEXT_MUTED),
                )
                .push(
                    text(
                        self.org
                            .updated_at
                            .as_deref()
                            .map(|value| format!("LAST EVENT {}", value))
                            .unwrap_or_else(|| "LAST EVENT pending".to_string()),
                    )
                    .size(11)
                    .style(TEXT_MUTED),
                )
                .into()
        };

        let _footer = container(footer_content)
            .padding(self.outer_padding())
            .style(footer_style);

        let shell: Element<'_, Message> = if breakpoint.is_tablet_or_smaller() {
            container(self.responsive_body())
                .height(Length::Fill)
                .into()
        } else {
            let sidebar = container(self.sidebar_nav())
                .width(Length::Fixed(if breakpoint == Breakpoint::Ultrawide {
                    260.0
                } else {
                    244.0
                }))
                .height(Length::Fill)
                .style(sidebar_style);
            Row::new()
                .push(sidebar)
                .push(container(self.active_section_view()).height(Length::Fill))
                .into()
        };

        container(shell)
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
    fn breakpoint(&self) -> Breakpoint {
        Breakpoint::from_width(self.viewport_width)
    }

    fn density(&self) -> DensityMode {
        match self.breakpoint() {
            Breakpoint::MobileSmall | Breakpoint::MobileLarge | Breakpoint::Laptop => {
                DensityMode::Compact
            }
            Breakpoint::Ultrawide => DensityMode::Expanded,
            _ => DensityMode::Balanced,
        }
    }

    fn outer_padding(&self) -> [u16; 2] {
        match self.breakpoint() {
            Breakpoint::MobileSmall | Breakpoint::MobileLarge => [12, 14],
            Breakpoint::Tablet => [14, 18],
            Breakpoint::Ultrawide => [18, 40],
            _ => [16, 28],
        }
    }

    fn panel_padding(&self) -> u16 {
        match self.density() {
            DensityMode::Compact => 12,
            DensityMode::Balanced => 16,
            DensityMode::Expanded => 18,
        }
    }

    fn command_stream_height(&self) -> f32 {
        match self.breakpoint() {
            Breakpoint::MobileSmall | Breakpoint::MobileLarge => 260.0,
            Breakpoint::Tablet => 300.0,
            Breakpoint::Ultrawide => 380.0,
            _ => 250.0,
        }
    }

    fn task_panel_height(&self) -> f32 {
        match self.breakpoint() {
            Breakpoint::MobileSmall | Breakpoint::MobileLarge => 300.0,
            Breakpoint::Tablet => 320.0,
            Breakpoint::Ultrawide => 380.0,
            _ => 250.0,
        }
    }

    fn responsive_body(&self) -> Element<'_, Message> {
        match self.breakpoint() {
            Breakpoint::MobileSmall | Breakpoint::MobileLarge => scrollable(
                Column::new()
                    .spacing(12)
                    .padding(self.panel_padding())
                    .push(self.sidebar_nav())
                    .push(self.active_section_view()),
            )
            .height(Length::Fill)
            .into(),
            Breakpoint::Tablet => scrollable(
                Column::new()
                    .spacing(14)
                    .padding(self.panel_padding())
                    .push(self.sidebar_nav())
                    .push(self.active_section_view()),
            )
            .height(Length::Fill)
            .into(),
            _ => {
                let content = Row::new()
                    .push(
                        container(self.sidebar_nav())
                            .width(Length::Fixed(
                                if self.breakpoint() == Breakpoint::Ultrawide {
                                    230.0
                                } else {
                                    198.0
                                },
                            ))
                            .style(sidebar_style),
                    )
                    .push(
                        container(self.active_section_view())
                            .width(Length::FillPortion(
                                if self.breakpoint() == Breakpoint::Ultrawide {
                                    6
                                } else {
                                    4
                                },
                            ))
                            .style(panel_center_style),
                    );
                container(content).height(Length::Fill).into()
            }
        }
    }

    fn sidebar_nav(&self) -> Element<'_, Message> {
        let items = [
            (NexusIcon::Message, SidebarSection::Conversation),
            (NexusIcon::Task, SidebarSection::Missions),
            (NexusIcon::Settings, SidebarSection::Settings),
        ];
        let mut nav = Column::new()
            .spacing(13)
            .padding(if self.breakpoint().is_tablet_or_smaller() {
                12
            } else {
                20
            })
            .push(
                Row::new()
                    .spacing(12)
                    .align_items(Alignment::Center)
                    .push(
                        container(text("N").size(23).style(CYAN))
                            .padding(10)
                            .style(brand_mark_style),
                    )
                    .push(
                        Column::new()
                            .spacing(5)
                            .push(text("NEXUS").size(20).style(TEXT_PRIMARY))
                            .push(
                                Row::new()
                                    .spacing(6)
                                    .align_items(Alignment::Center)
                                    .push(container(Space::new(7, 7)).style(
                                        if self.status == "ONLINE" {
                                            success_dot_style
                                        } else {
                                            error_dot_style
                                        },
                                    ))
                                    .push(
                                        text(if self.status == "ONLINE" {
                                            "Online"
                                        } else {
                                            "Offline"
                                        })
                                        .size(11)
                                        .style(TEXT_MUTED),
                                    ),
                            ),
                    ),
            )
            .push(Space::with_height(Length::Fixed(26.0)));

        for (icon, section) in items {
            nav = nav.push(sidebar_item(
                icon,
                section.label(),
                self.active_section == section,
                Message::SelectSection(section),
            ));
        }

        nav = nav.push(Space::with_height(Length::Fill)).push(
            container(
                Column::new()
                    .spacing(14)
                    .push(
                        Row::new()
                            .spacing(9)
                            .align_items(Alignment::Center)
                            .push(icon(NexusIcon::Sparkle, 18, CYAN))
                            .push(text("NEXUS Pro").size(14).style(CYAN)),
                    )
                    .push(
                        text("Seu assistente inteligente sempre pronto para ajudar.")
                            .size(12)
                            .style(TEXT_SECONDARY),
                    )
                    .push(
                        container(
                            Row::new()
                                .align_items(Alignment::Center)
                                .push(text("Saiba mais").size(13).style(TEXT_PRIMARY))
                                .push(Space::with_width(Length::Fill))
                                .push(icon(NexusIcon::ChevronRight, 16, TEXT_PRIMARY)),
                        )
                        .padding([10, 18])
                        .width(Length::Fill)
                        .style(sidebar_learn_more_style),
                    ),
            )
            .padding(16)
            .style(sidebar_card_style),
        );

        if self.breakpoint().is_tablet_or_smaller() {
            scrollable(nav)
                .height(Length::Fixed(if self.breakpoint().is_mobile() {
                    300.0
                } else {
                    360.0
                }))
                .into()
        } else {
            nav.height(Length::Fill).into()
        }
    }

    fn active_section_view(&self) -> Element<'_, Message> {
        let content: Element<'_, Message> = match self.active_section {
            SidebarSection::Overview => self.overview_page(),
            SidebarSection::Conversation => self.conversation_page(),
            SidebarSection::Missions => self.missions_page(),
            SidebarSection::Swarm => self.swarm_page(),
            SidebarSection::Executions => self.executions_page(),
            SidebarSection::Approvals => self.approvals_page(),
            SidebarSection::Incidents => self.incidents_page(),
            SidebarSection::Observer => self.observer_page(),
            SidebarSection::Telemetry => self.telemetry_page(),
            SidebarSection::Memory => self.memory_page(),
            SidebarSection::Settings => self.settings_page(),
        };
        if self.active_section == SidebarSection::Conversation {
            return container(content)
                .height(Length::Fill)
                .style(panel_center_style)
                .into();
        }

        container(content)
            .padding(self.panel_padding())
            .height(Length::Fill)
            .style(panel_center_style)
            .into()
    }

    fn overview_page(&self) -> Element<'_, Message> {
        if self.breakpoint().is_tablet_or_smaller() {
            scrollable(
                Column::new()
                    .spacing(14)
                    .push(page_header(
                        "Visão Geral",
                        "Estado consolidado do NEXUS, missões e sinais operacionais.",
                    ))
                    .push(self.mission_focus_card())
                    .push(self.hybrid_intelligence_panel())
                    .push(self.system_status_panel())
                    .push(self.mission_flow_visualization())
                    .push(self.execution_snapshot_panel())
                    .push(self.cognitive_team_snapshot_panel())
                    .push(self.incident_status_panel())
                    .push(self.cognitive_telemetry_panel())
                    .push(self.recent_activity_panel())
                    .push(self.mission_timeline_panel()),
            )
            .height(Length::Fill)
            .into()
        } else {
            scrollable(
                Column::new()
                    .spacing(14)
                    .push(page_header(
                        "Visão Geral",
                        "Estado consolidado do NEXUS, missões e sinais operacionais.",
                    ))
                    .push(
                        Row::new()
                            .spacing(14)
                            .push(
                                container(self.mission_focus_card()).width(Length::FillPortion(7)),
                            )
                            .push(
                                Column::new()
                                    .spacing(14)
                                    .push(self.hybrid_intelligence_panel())
                                    .push(self.system_status_panel())
                                    .width(Length::FillPortion(3)),
                            ),
                    )
                    .push(self.mission_flow_visualization())
                    .push(
                        Row::new()
                            .spacing(14)
                            .push(
                                container(self.execution_snapshot_panel())
                                    .width(Length::FillPortion(3)),
                            )
                            .push(
                                container(self.cognitive_team_snapshot_panel())
                                    .width(Length::FillPortion(3)),
                            )
                            .push(
                                Column::new()
                                    .spacing(14)
                                    .push(self.incident_status_panel())
                                    .push(self.cognitive_telemetry_panel())
                                    .width(Length::FillPortion(2)),
                            ),
                    )
                    .push(
                        Row::new()
                            .spacing(14)
                            .push(
                                container(self.mission_timeline_panel())
                                    .width(Length::FillPortion(5)),
                            )
                            .push(
                                container(self.recent_activity_panel())
                                    .width(Length::FillPortion(3)),
                            ),
                    ),
            )
            .height(Length::Fill)
            .into()
        }
    }

    fn mission_focus_card(&self) -> Element<'_, Message> {
        let goal = self
            .org
            .swarm
            .as_ref()
            .and_then(|swarm| swarm.current_goal.as_deref())
            .map(|goal| trim_text(goal, 96))
            .unwrap_or_else(|| "Aguardando nova missão do swarm".to_string());
        let progress = self.mission_progress_percent();
        let progress_fill = (progress * 3.0).clamp(24.0, 300.0);
        let started_at = self
            .org
            .commands
            .first()
            .map(|command| trim_text(&command.created_at, 19))
            .or_else(|| {
                self.org
                    .swarm
                    .as_ref()
                    .and_then(|swarm| swarm.tasks.first())
                    .map(timestamp_for_task)
            })
            .unwrap_or_else(|| "aguardando".to_string());
        let active_step = self.active_mission_step();
        let status = if self.org.approvals.is_empty() {
            "Em execução"
        } else {
            "Aguardando aprovação"
        };

        container(
            Row::new()
                .spacing(22)
                .align_items(Alignment::Center)
                .push(
                    container(Space::new(88, 88))
                        .width(Length::Fixed(104.0))
                        .height(Length::Fixed(104.0))
                        .style(orb_style),
                )
                .push(
                    Column::new()
                        .spacing(14)
                        .width(Length::Fill)
                        .push(text("MISSÃO ATIVA").size(10).style(ACCENT))
                        .push(text(goal).size(24).style(TEXT_PRIMARY))
                        .push(
                            text("Garantir integração, estabilidade e segurança antes da liberação para produção.")
                                .size(12)
                                .style(TEXT_SECONDARY),
                        )
                        .push(
                            container(
                                Row::new()
                                    .spacing(18)
                                    .align_items(Alignment::Center)
                                    .push(
                                        Column::new()
                                            .spacing(7)
                                            .width(Length::FillPortion(2))
                                            .push(text("Progresso geral").size(10).style(TEXT_MUTED))
                                            .push(
                                                Row::new()
                                                    .spacing(8)
                                                    .align_items(Alignment::Center)
                                                    .push(
                                                        container(Space::new(progress_fill, 5))
                                                            .style(meter_fill_accent_style),
                                                    )
                                                    .push(
                                                        container(Space::with_width(Length::Fill).height(5))
                                                            .style(meter_track_style),
                                                    )
                                                    .push(
                                                        text(format!("{:.0}%", progress))
                                                            .size(11)
                                                            .style(TEXT_PRIMARY),
                                                    ),
                                            ),
                                    )
                                    .push(mission_fact("Status", status.to_string(), SUCCESS))
                                    .push(mission_fact(
                                        "Responsável",
                                        role_display_name(active_step).to_string(),
                                        ACCENT,
                                    ))
                                    .push(mission_fact("Iniciado em", started_at, TEXT_SECONDARY)),
                            )
                            .padding(12)
                            .width(Length::Fill)
                            .style(mission_meta_style),
                        ),
                ),
        )
        .padding(24)
        .width(Length::Fill)
        .style(mission_card_style)
        .into()
    }

    fn hybrid_intelligence_panel(&self) -> Element<'_, Message> {
        let local = self
            .product
            .as_ref()
            .and_then(|status| status.models.local.selected_model.as_deref())
            .unwrap_or("qwen2.5:3b");
        let cloud = self
            .product
            .as_ref()
            .map(|status| status.models.cloud.model.as_str())
            .unwrap_or("GPT-5.5");
        let mode = self
            .product
            .as_ref()
            .map(|status| status.models.mode.as_str())
            .unwrap_or("Hybrid Adaptive");

        container(
            Column::new()
                .spacing(12)
                .push(text("INTELIGÊNCIA HÍBRIDA").size(12).style(TEXT_PRIMARY))
                .push(
                    Row::new()
                        .spacing(10)
                        .push(ai_route_card(
                            "Local AI",
                            trim_text(local, 18),
                            "Rápida · Privada · Offline",
                            CYAN,
                        ))
                        .push(ai_route_card(
                            "Cloud AI",
                            trim_text(cloud, 18),
                            "Raciocínio avançado · Estratégica",
                            PURPLE,
                        )),
                )
                .push(
                    container(
                        Row::new()
                            .spacing(8)
                            .align_items(Alignment::Center)
                            .push(text("⌘").size(14).style(PURPLE))
                            .push(
                                text(format!("Modo atual: {}", mode))
                                    .size(11)
                                    .style(TEXT_SECONDARY),
                            ),
                    )
                    .padding([8, 10])
                    .width(Length::Fill)
                    .style(mode_banner_style),
                ),
        )
        .padding(14)
        .width(Length::Fill)
        .style(section_style)
        .into()
    }

    fn system_status_panel(&self) -> Element<'_, Message> {
        let daemon = self
            .product
            .as_ref()
            .map(|status| friendly_status(&status.daemon.status))
            .unwrap_or_else(|| friendly_status(&self.status));
        let uptime = self.session_start.elapsed();
        let verifications = self
            .org
            .memory
            .as_ref()
            .map(|memory| memory.verifications)
            .unwrap_or(self.org.verifications.len() as i64);

        container(
            Column::new()
                .spacing(10)
                .push(text("STATUS DO SISTEMA").size(12).style(TEXT_PRIMARY))
                .push(system_status_row("Daemon", daemon, SUCCESS))
                .push(system_status_row(
                    "Uptime",
                    format!(
                        "{}h {}m",
                        uptime.as_secs() / 3600,
                        (uptime.as_secs() / 60) % 60
                    ),
                    TEXT_SECONDARY,
                ))
                .push(system_meter_row("Uso de CPU", self.cpu_usage))
                .push(system_meter_row("Uso de RAM", self.ram_usage))
                .push(system_meter_row(
                    "Swarm Saturation",
                    self.swarm_saturation_value(),
                ))
                .push(system_status_row(
                    "Verificações",
                    verifications.to_string(),
                    TEXT_SECONDARY,
                )),
        )
        .padding(14)
        .width(Length::Fill)
        .style(section_style)
        .into()
    }

    fn execution_snapshot_panel(&self) -> Element<'_, Message> {
        let mut body = Column::new().spacing(10);
        if let Some(command) = self.org.commands.first() {
            let verification = self.latest_verification_status();
            body = body
                .push(
                    Row::new()
                        .spacing(10)
                        .align_items(Alignment::Center)
                        .push(icon(NexusIcon::ArrowUpRight, 16, TEXT_MUTED))
                        .push(
                            text(human_command_label(&command.command))
                                .size(15)
                                .style(TEXT_PRIMARY),
                        ),
                )
                .push(Rule::horizontal(1).style(rule_style))
                .push(runtime_line(
                    "Resultado",
                    &friendly_status(&command.status),
                    status_color(&command.status),
                ))
                .push(runtime_line(
                    "Duração",
                    &command
                        .duration_ms
                        .map(|ms| format!("{}ms", ms))
                        .unwrap_or_else(|| "em andamento".to_string()),
                    TEXT_SECONDARY,
                ))
                .push(runtime_line(
                    "Verificação",
                    &friendly_status(&verification),
                    status_color(&verification),
                ))
                .push(
                    container(
                        Row::new()
                            .spacing(10)
                            .align_items(Alignment::Center)
                            .push(text("Próximo passo").size(10).style(TEXT_MUTED))
                            .push(
                                text("Aguardando próxima missão do swarm")
                                    .size(10)
                                    .style(TEXT_SECONDARY),
                            ),
                    )
                    .padding(10)
                    .width(Length::Fill)
                    .style(task_row_style),
                );
        } else {
            body = body.push(empty_state(
                "Nenhuma execução atual.",
                "A execução aparece aqui quando um comando aprovado roda de verdade.",
            ));
        }

        container(
            Column::new()
                .spacing(12)
                .push(text("EXECUÇÃO ATUAL").size(12).style(TEXT_PRIMARY))
                .push(body),
        )
        .padding(14)
        .width(Length::Fill)
        .style(section_style)
        .into()
    }

    fn cognitive_team_snapshot_panel(&self) -> Element<'_, Message> {
        let mut list = Column::new().spacing(8);
        if let Some(swarm) = &self.org.swarm {
            for agent in swarm.agents.iter().take(5) {
                list = list.push(team_member_row(
                    role_display_name(&agent.role),
                    role_action_label(&agent.role),
                    friendly_status(&agent.status),
                    model_for_agent(&agent.role, self.product.as_ref()),
                ));
            }
        }
        if self
            .org
            .swarm
            .as_ref()
            .map(|swarm| swarm.agents.is_empty())
            .unwrap_or(true)
        {
            for role in ["planner", "observer", "security", "reviewer", "devops"] {
                list = list.push(team_member_row(
                    role_display_name(role),
                    role_action_label(role),
                    "aguardando".to_string(),
                    model_for_agent(role, self.product.as_ref()),
                ));
            }
        }

        container(
            Column::new()
                .spacing(12)
                .push(
                    Row::new()
                        .push(text("EQUIPE COGNITIVA").size(12).style(TEXT_PRIMARY))
                        .push(Space::with_width(Length::Fill))
                        .push(text("Ver todos").size(10).style(ACCENT)),
                )
                .push(list),
        )
        .padding(14)
        .width(Length::Fill)
        .style(section_style)
        .into()
    }

    fn incident_status_panel(&self) -> Element<'_, Message> {
        let content: Element<'_, Message> = if self.org.incidents.is_empty() {
            container(
                Row::new()
                    .spacing(12)
                    .align_items(Alignment::Center)
                    .push(
                        container(icon(NexusIcon::Check, 18, TEXT_PRIMARY))
                            .padding(8)
                            .style(success_shield_style),
                    )
                    .push(
                        Column::new()
                            .spacing(4)
                            .push(text("Nenhum incidente ativo").size(12).style(SUCCESS))
                            .push(
                                text("Tudo funcionando normalmente.")
                                    .size(10)
                                    .style(TEXT_MUTED),
                            ),
                    ),
            )
            .padding(10)
            .width(Length::Fill)
            .style(task_row_style)
            .into()
        } else {
            let incident = self.org.incidents.first().expect("checked not empty");
            container(
                Column::new()
                    .spacing(4)
                    .push(
                        text(incident.severity.to_uppercase())
                            .size(10)
                            .style(severity_color(&incident.severity)),
                    )
                    .push(
                        text(trim_text(&incident.message, 88))
                            .size(12)
                            .style(TEXT_PRIMARY),
                    )
                    .push(
                        text(trim_text(&incident.module, 40))
                            .size(10)
                            .style(TEXT_MUTED),
                    ),
            )
            .padding(10)
            .width(Length::Fill)
            .style(incident_row_style)
            .into()
        };

        container(
            Column::new()
                .spacing(10)
                .push(
                    Row::new()
                        .push(text("INCIDENTES").size(12).style(TEXT_PRIMARY))
                        .push(Space::with_width(Length::Fill))
                        .push(text("Ver todos").size(10).style(ACCENT)),
                )
                .push(content),
        )
        .padding(14)
        .width(Length::Fill)
        .style(section_style)
        .into()
    }

    fn recent_activity_panel(&self) -> Element<'_, Message> {
        let mut activity = Column::new().spacing(8);
        for item in self.visible_activity().iter().rev().take(5) {
            activity = activity.push(
                Row::new()
                    .spacing(10)
                    .align_items(Alignment::Center)
                    .push(
                        text(trim_text(&item.timestamp, 5))
                            .size(10)
                            .style(TEXT_SECONDARY),
                    )
                    .push(text("●").size(11).style(activity_color(&item.level)))
                    .push(
                        text(trim_text(&item.label, 42))
                            .size(11)
                            .style(TEXT_SECONDARY),
                    ),
            );
        }

        container(
            Column::new()
                .spacing(10)
                .push(
                    Row::new()
                        .push(text("ATIVIDADE RECENTE").size(12).style(TEXT_PRIMARY))
                        .push(Space::with_width(Length::Fill))
                        .push(text("Ver todas").size(10).style(ACCENT)),
                )
                .push(activity),
        )
        .padding(14)
        .width(Length::Fill)
        .style(section_style)
        .into()
    }

    fn mission_timeline_panel(&self) -> Element<'_, Message> {
        let command_time = self
            .org
            .commands
            .first()
            .map(|command| trim_text(&command.created_at, 5))
            .unwrap_or_else(|| current_time().chars().take(5).collect());
        let verification_time = self
            .latest_verification()
            .map(|item| trim_text(&item.created_at, 5))
            .unwrap_or_else(|| "--:--".to_string());
        let points = Row::new()
            .spacing(20)
            .align_items(Alignment::Center)
            .push(timeline_point(&command_time, "Missão", "iniciada", ACCENT))
            .push(timeline_point("agora", "Planner", "organizou etapas", CYAN))
            .push(timeline_point("agora", "Execução", "realizada", WARNING))
            .push(timeline_point(
                &verification_time,
                "Verificação",
                "concluída",
                SUCCESS,
            ))
            .push(timeline_point(
                "--:--",
                "Próximo",
                "aguardando missão",
                TEXT_MUTED,
            ));

        let content: Element<'_, Message> = if self.breakpoint().is_mobile() {
            scrollable(points)
                .direction(scrollable::Direction::Horizontal(
                    scrollable::Properties::new().width(4),
                ))
                .height(Length::Fixed(92.0))
                .into()
        } else {
            points.into()
        };

        container(
            Column::new()
                .spacing(12)
                .push(text("LINHA DO TEMPO").size(12).style(TEXT_PRIMARY))
                .push(content),
        )
        .padding(14)
        .width(Length::Fill)
        .style(section_style)
        .into()
    }

    fn mission_progress_percent(&self) -> f32 {
        if self
            .latest_verification()
            .map(|item| item.status == "passed")
            .unwrap_or(false)
        {
            return 100.0;
        }
        match self.active_mission_step() {
            "planner" => 28.0,
            "devops" => 48.0,
            "reviewer" => 72.0,
            "security" => 82.0,
            "runtime" => 64.0,
            "ceo" => 16.0,
            _ => 35.0,
        }
    }

    fn active_operations_count(&self) -> usize {
        self.org
            .swarm
            .as_ref()
            .map(|swarm| {
                swarm
                    .tasks
                    .iter()
                    .filter(|task| task.status != "completed" && task.status != "done")
                    .count()
            })
            .unwrap_or(0)
    }

    fn swarm_saturation_value(&self) -> f32 {
        self.org
            .swarm
            .as_ref()
            .map(|swarm| {
                if swarm.agents.is_empty() {
                    0.0
                } else {
                    let busy = swarm
                        .agents
                        .iter()
                        .filter(|agent| agent.status != "idle")
                        .count() as f32;
                    (busy / swarm.agents.len() as f32) * 100.0
                }
            })
            .unwrap_or_else(|| (self.active_operations_count() as f32 * 14.0).min(100.0))
    }

    fn conversation_page(&self) -> Element<'_, Message> {
        Column::new()
            .push(self.chat_top_bar())
            .push(Rule::horizontal(1).style(rule_style))
            .push(self.chat_workspace())
            .height(Length::Fill)
            .into()
    }

    fn chat_top_bar(&self) -> Element<'_, Message> {
        let is_online = self.status == "ONLINE";
        let status = container(
            Row::new()
                .spacing(9)
                .align_items(Alignment::Center)
                .push(container(Space::new(10, 10)).style(if is_online {
                    success_dot_style
                } else {
                    error_dot_style
                }))
                .push(
                    text(if is_online { "Online" } else { "Offline" })
                        .size(14)
                        .style(TEXT_PRIMARY),
                )
                .push(icon(NexusIcon::ChevronDown, 14, CYAN)),
        )
        .padding([9, 15])
        .style(chat_status_pill_style);

        let avatar = container(text("U").size(15).style(TEXT_PRIMARY))
            .padding(13)
            .style(user_avatar_style);

        container(
            Row::new()
                .spacing(16)
                .align_items(Alignment::Center)
                .push(Space::with_width(Length::Fill))
                .push(status)
                .push(avatar),
        )
        .padding(if self.breakpoint().is_mobile() {
            [12, 16]
        } else {
            [18, 28]
        })
        .height(Length::Fixed(if self.breakpoint().is_mobile() {
            68.0
        } else {
            82.0
        }))
        .width(Length::Fill)
        .style(chat_top_bar_style)
        .into()
    }

    fn chat_workspace(&self) -> Element<'_, Message> {
        let show_starter = self.messages.len() <= 1 && !self.is_thinking;
        let logo_size = if self.breakpoint().is_mobile() {
            26
        } else {
            38
        };
        let title_size = if self.breakpoint().is_mobile() {
            26
        } else {
            34
        };
        let subtitle_size = if self.breakpoint().is_mobile() {
            14
        } else {
            17
        };
        let mut content = Column::new()
            .spacing(if self.breakpoint().is_mobile() {
                20
            } else {
                28
            })
            .align_items(Alignment::Center)
            .padding(if self.breakpoint().is_mobile() {
                [18, 0]
            } else {
                [30, 0]
            });

        if show_starter {
            content = content.push(
                Column::new()
                    .spacing(18)
                    .align_items(Alignment::Center)
                    .push(
                        container(text("N").size(logo_size).style(CYAN))
                            .padding(if self.breakpoint().is_mobile() { 17 } else { 22 })
                            .style(chat_logo_style),
                    )
                    .push(
                        Column::new()
                            .spacing(8)
                            .align_items(Alignment::Center)
                            .push(
                                text("Como posso ajudar hoje?")
                                    .size(title_size)
                                    .style(TEXT_PRIMARY),
                            )
                            .push(
                                text("Posso resumir arquivos, organizar tarefas ou responder perguntas.")
                                    .size(subtitle_size)
                                    .style(TEXT_SECONDARY),
                            ),
                    ),
            );
            content = content.push(self.prompt_grid());
        } else {
            content = content.push(Space::with_height(Length::Fixed(12.0)));
        }

        content = content.push(self.message_thread());

        container(
            Column::new()
                .align_items(Alignment::Center)
                .height(Length::Fill)
                .push(
                    scrollable(content)
                        .id(scrollable::Id::new(SCROLLABLE_ID))
                        .height(Length::Fill)
                        .width(Length::Fill),
                )
                .push(if let Some((cmd_id, cmd_text, risk)) = &self.pending_approval {
                    container(
                        Column::new()
                            .spacing(12)
                            .push(text(format!("Ação Perigosa: {:?}", risk)).size(16).style(DANGER))
                            .push(text(cmd_text).size(14).style(TEXT_PRIMARY))
                            .push(Row::new()
                                .spacing(12)
                                .push(button(text("Aprovar").style(iced::Color::WHITE)).style(theme::Button::Positive).on_press(Message::ReplyApproval(cmd_id.clone(), true)))
                                .push(button(text("Negar").style(iced::Color::WHITE)).style(theme::Button::Destructive).on_press(Message::ReplyApproval(cmd_id.clone(), false)))
                            )
                    )
                    .padding(16)
                    .width(self.chat_stage_length())
                    .style(chat_input_shell_style)
                } else {
                    container(Space::new(0, 0))
                })
                .push(self.chat_input_bar())
                .push(
                    container(
                        Row::new()
                            .spacing(7)
                            .align_items(Alignment::Center)
                            .push(icon(NexusIcon::Lock, 12, TEXT_MUTED))
                            .push(
                                text("O NEXUS pode cometer erros. Verifique as informações importantes.")
                                    .size(11)
                                    .width(Length::Fill)
                                    .style(TEXT_MUTED),
                            ),
                    )
                    .padding([12, 0]),
                ),
        )
        .padding(if self.breakpoint().is_mobile() {
            [0, 14]
        } else {
            [0, 28]
        })
        .height(Length::Fill)
        .width(Length::Fill)
        .style(chat_workspace_style)
        .into()
    }

    fn chat_stage_width(&self) -> f32 {
        match self.breakpoint() {
            Breakpoint::Ultrawide => 980.0,
            Breakpoint::Desktop => 930.0,
            Breakpoint::Laptop => 820.0,
            _ => 0.0,
        }
    }

    fn chat_stage_length(&self) -> Length {
        if self.breakpoint().is_tablet_or_smaller() {
            Length::Fill
        } else {
            Length::Fixed(self.chat_stage_width())
        }
    }

    fn prompt_grid(&self) -> Element<'_, Message> {
        let cards = [
            (
                NexusIcon::Document,
                "Resumir documento",
                "Resuma arquivos e textos longos.",
                "Quero um resumo deste projeto e os próximos passos.",
            ),
            (
                NexusIcon::List,
                "Organizar tarefas",
                "Organize suas tarefas e prioridades.",
                "Organize minhas tarefas por prioridade.",
            ),
            (
                NexusIcon::Circle,
                "Explicar projeto",
                "Explique ideias e conceitos complexos.",
                "Explique este projeto em linguagem simples.",
            ),
            (
                NexusIcon::ArrowUpRight,
                "Criar plano",
                "Monte um plano passo a passo.",
                "Crie um plano de ação para melhorar este projeto.",
            ),
        ];

        if self.breakpoint().is_tablet_or_smaller() {
            let mut column = Column::new().spacing(12).width(Length::Fill);
            for (icon, title, detail, prompt) in cards {
                column = column.push(prompt_card(icon, title, detail, prompt, Length::Fill));
            }
            container(column).width(self.chat_stage_length()).into()
        } else {
            let mut row = Row::new().spacing(16).width(self.chat_stage_length());
            for (icon, title, detail, prompt) in cards {
                row = row.push(prompt_card(
                    icon,
                    title,
                    detail,
                    prompt,
                    Length::FillPortion(1),
                ));
            }
            row.into()
        }
    }

    fn message_thread(&self) -> Element<'_, Message> {
        let mut messages = Column::new().spacing(18).width(self.chat_stage_length());

        for msg in self.messages.iter().rev().take(8).rev() {
            messages = messages.push(chat_message_row(
                msg,
                self.breakpoint().is_tablet_or_smaller(),
            ));
        }

        if self.is_thinking {
            messages = messages.push(thinking_message_row(
                self.tick_counter,
                self.breakpoint().is_tablet_or_smaller(),
            ));
        }

        container(messages).width(self.chat_stage_length()).into()
    }

    fn chat_input_bar(&self) -> Element<'_, Message> {
        let input = text_input("Envie uma mensagem...", &self.input_value)
            .on_input(Message::InputChanged)
            .on_submit(Message::Submit)
            .padding(12)
            .size(15)
            .width(Length::Fill)
            .style(theme::TextInput::Custom(Box::new(ChatTextInputStyle)));

        let send = icon_button(
            NexusIcon::Send,
            "Enviar mensagem",
            (!self.is_thinking).then_some(Message::Submit),
            IconButtonStyle::primary(48.0, 21),
        );

        container(
            Row::new()
                .spacing(14)
                .align_items(Alignment::Center)
                .push(icon_button(
                    NexusIcon::Paperclip,
                    "Anexar arquivo",
                    None,
                    IconButtonStyle::subtle(44.0, 20),
                ))
                .push(input)
                .push(icon_button(
                    NexusIcon::Mic,
                    "Usar voz",
                    None,
                    IconButtonStyle::flat(40.0, 20),
                ))
                .push(send),
        )
        .padding([12, 14])
        .width(self.chat_stage_length())
        .height(Length::Fixed(72.0))
        .style(chat_input_shell_style)
        .into()
    }

    fn dashboard_header(&self) -> Element<'_, Message> {
        let is_online = self.status == "ONLINE";
        let status = container(
            Row::new()
                .spacing(9)
                .align_items(Alignment::Center)
                .push(container(Space::new(10, 10)).style(if is_online {
                    success_dot_style
                } else {
                    danger_dot_style
                }))
                .push(
                    text(if is_online {
                        "Sistema ativo"
                    } else {
                        "Sistema offline"
                    })
                    .size(14)
                    .style(if is_online { SUCCESS } else { DANGER }),
                ),
        )
        .padding([10, 18])
        .style(nexus_active_pill_style);

        Row::new()
            .spacing(20)
            .align_items(Alignment::Center)
            .push(
                Column::new()
                    .spacing(6)
                    .push(text("Painel do NEXUS").size(34).style(TEXT_PRIMARY))
                    .push(
                        text("Resumo do sistema e atividades em andamento")
                            .size(15)
                            .style(TEXT_SECONDARY),
                    ),
            )
            .push(Space::with_width(Length::Fill))
            .push(status)
            .into()
    }

    fn nexus_status_summary_card(&self) -> Element<'_, Message> {
        let healthy = self.status == "ONLINE" && self.org.incidents.is_empty();
        let activity = if self.is_thinking {
            ("Alta", "Processando pedido", WARNING)
        } else if self.active_operations_count() > 0 {
            ("Média", "Operação em andamento", ACCENT)
        } else {
            ("Baixa", "Tudo tranquilo", SUCCESS)
        };

        container(
            Column::new()
                .spacing(22)
                .align_items(Alignment::Center)
                .push(
                    container(
                        text(if healthy { "✓" } else { "!" })
                            .size(42)
                            .style(if healthy { CYAN } else { WARNING }),
                    )
                    .padding(20)
                    .style(nexus_status_icon_style),
                )
                .push(
                    Column::new()
                        .spacing(8)
                        .align_items(Alignment::Center)
                        .push(
                            text(if healthy {
                                "Tudo funcionando normalmente"
                            } else {
                                "Atenção necessária"
                            })
                            .size(26)
                            .style(TEXT_PRIMARY),
                        )
                        .push(
                            text(if healthy {
                                "O NEXUS está pronto para ajudar você."
                            } else {
                                "Há sinais que precisam ser revisados."
                            })
                            .size(14)
                            .style(TEXT_SECONDARY),
                        ),
                )
                .push(
                    Row::new()
                        .spacing(24)
                        .align_items(Alignment::Center)
                        .push(nexus_summary_metric(
                            "↗",
                            "Desempenho",
                            performance_label(self.cpu_usage),
                            "Sistema responsivo",
                            ACCENT,
                        ))
                        .push(container(Space::new(1, 72)).style(vertical_divider_style))
                        .push(nexus_summary_metric(
                            "▣",
                            "Memória",
                            format!("{:.0}%", self.ram_usage),
                            "Uso equilibrado",
                            PURPLE,
                        ))
                        .push(container(Space::new(1, 72)).style(vertical_divider_style))
                        .push(nexus_summary_metric(
                            "~",
                            "Atividade",
                            activity.0.to_string(),
                            activity.1,
                            activity.2,
                        )),
                ),
        )
        .padding(24)
        .width(Length::Fill)
        .style(nexus_main_card_style)
        .into()
    }

    fn nexus_current_action_card(&self) -> Element<'_, Message> {
        let action = if self.is_thinking {
            self.processing_stage()
        } else if let Some(command) = self.org.commands.first() {
            format!("Última execução: {}", friendly_status(&command.status))
        } else {
            "Aguardando seu pedido".to_string()
        };
        let detail = if self.is_thinking {
            "Estou processando a solicitação e volto com evidência quando concluir."
        } else {
            "Fale comigo ao lado e eu te ajudo."
        };

        container(
            Row::new()
                .spacing(22)
                .align_items(Alignment::Center)
                .push(
                    container(text("✦").size(34).style(CYAN))
                        .padding(22)
                        .style(nexus_status_icon_style),
                )
                .push(
                    Column::new()
                        .spacing(8)
                        .push(
                            text("O que o NEXUS está fazendo agora")
                                .size(18)
                                .style(TEXT_PRIMARY),
                        )
                        .push(text(action).size(24).style(CYAN))
                        .push(text(detail).size(14).style(TEXT_SECONDARY)),
                ),
        )
        .padding(22)
        .width(Length::Fill)
        .style(nexus_card_style)
        .into()
    }

    fn nexus_updates_card(&self) -> Element<'_, Message> {
        let mut updates = Column::new().spacing(14);
        for item in self.visible_activity().iter().rev().take(3) {
            updates = updates.push(
                Row::new()
                    .spacing(14)
                    .align_items(Alignment::Center)
                    .push(
                        container(
                            text(activity_symbol(&item.level))
                                .size(16)
                                .style(activity_color(&item.level)),
                        )
                        .padding(8)
                        .style(nexus_update_icon_style),
                    )
                    .push(
                        Column::new()
                            .spacing(3)
                            .push(
                                text(trim_text(&item.label, 44))
                                    .size(15)
                                    .style(TEXT_PRIMARY),
                            )
                            .push(text(trim_text(&item.detail, 78)).size(12).style(TEXT_MUTED)),
                    )
                    .push(Space::with_width(Length::Fill))
                    .push(
                        text(format!("Hoje, {}", trim_text(&item.timestamp, 5)))
                            .size(12)
                            .style(TEXT_MUTED),
                    ),
            );
        }

        container(
            Column::new()
                .spacing(16)
                .push(text("Últimas atualizações").size(18).style(TEXT_PRIMARY))
                .push(updates)
                .push(Rule::horizontal(1).style(rule_style))
                .push(
                    Row::new()
                        .align_items(Alignment::Center)
                        .push(Space::with_width(Length::Fill))
                        .push(text("Ver mais atualizações").size(13).style(CYAN))
                        .push(text("  >").size(15).style(CYAN))
                        .push(Space::with_width(Length::Fill)),
                ),
        )
        .padding(22)
        .width(Length::Fill)
        .style(nexus_card_style)
        .into()
    }

    fn nexus_chat_card(&self) -> Element<'_, Message> {
        let mut messages = Column::new().spacing(10);
        for msg in self.messages.iter().rev().take(5).rev() {
            let is_operator = msg.role == "OPERATOR";
            messages = messages.push(
                container(
                    Column::new()
                        .spacing(5)
                        .push(
                            text(if is_operator { "Você" } else { "NEXUS" })
                                .size(11)
                                .style(if is_operator { WARNING } else { CYAN }),
                        )
                        .push(
                            text(trim_text(&msg.content, 240))
                                .size(12)
                                .style(TEXT_SECONDARY),
                        ),
                )
                .padding(10)
                .width(Length::Fill)
                .style(if is_operator {
                    operator_bubble_modern
                } else {
                    nexus_bubble_modern
                }),
            );
        }

        let body: Element<'_, Message> = if self.messages.len() <= 1 && !self.is_thinking {
            container(
                Column::new()
                    .spacing(16)
                    .align_items(Alignment::Center)
                    .push(
                        container(icon(NexusIcon::Message, 36, CYAN))
                            .padding(24)
                            .style(nexus_status_icon_style),
                    )
                    .push(
                        text("Como posso ajudar você hoje?")
                            .size(18)
                            .style(TEXT_PRIMARY),
                    )
                    .push(
                        text("Envie sua mensagem e eu responderei o mais rápido possível.")
                            .size(13)
                            .style(TEXT_SECONDARY),
                    ),
            )
            .height(Length::Fill)
            .center_x()
            .center_y()
            .style(nexus_chat_empty_style)
            .into()
        } else {
            scrollable(messages).height(Length::Fill).into()
        };

        let mut send = button(text("Enviar  >").size(16))
            .padding([14, 18])
            .width(Length::Fill)
            .style(theme::Button::custom(PrimaryActionButtonStyle));
        if !self.is_thinking {
            send = send.on_press(Message::Submit);
        }

        container(
            Column::new()
                .spacing(18)
                .push(
                    Column::new()
                        .spacing(8)
                        .push(text("Fale com o NEXUS").size(26).style(TEXT_PRIMARY))
                        .push(
                            text("Estou aqui para ajudar. É só perguntar!")
                                .size(14)
                                .style(TEXT_SECONDARY),
                        ),
                )
                .push(body)
                .push(
                    text_input("Digite sua mensagem...", &self.input_value)
                        .on_input(Message::InputChanged)
                        .on_submit(Message::Submit)
                        .padding(16)
                        .width(Length::Fill),
                )
                .push(send),
        )
        .padding(24)
        .width(Length::Fill)
        .height(Length::Fill)
        .style(nexus_card_style)
        .into()
    }

    fn hud_telemetry_rail(&self) -> Element<'_, Message> {
        let runtime = self
            .org
            .commands
            .first()
            .map(|command| friendly_status(&command.status))
            .unwrap_or_else(|| "idle".to_string());
        let daemon = self
            .product
            .as_ref()
            .map(|status| friendly_status(&status.daemon.status))
            .unwrap_or_else(|| friendly_status(&self.status));
        let local = self
            .product
            .as_ref()
            .and_then(|status| status.models.local.selected_model.as_deref())
            .unwrap_or("local pending");
        let cloud = self
            .product
            .as_ref()
            .map(|status| status.models.cloud.model.as_str())
            .unwrap_or("cloud pending");

        container(
            Column::new()
                .spacing(10)
                .push(text("NEXUS SYSTEMS").size(13).style(CYAN))
                .push(hud_metric_tile(
                    "CORE",
                    daemon,
                    if self.status == "ONLINE" {
                        SUCCESS
                    } else {
                        DANGER
                    },
                ))
                .push(hud_meter_tile("CPU LOAD", self.cpu_usage, ACCENT))
                .push(hud_meter_tile("MEMORY", self.ram_usage, WARNING))
                .push(hud_metric_tile("RUNTIME", runtime, TEXT_SECONDARY))
                .push(hud_metric_tile(
                    "MODEL",
                    format!("{} / {}", trim_text(local, 14), trim_text(cloud, 14)),
                    TEXT_SECONDARY,
                )),
        )
        .padding(14)
        .width(Length::Fill)
        .style(hud_panel_style)
        .into()
    }

    fn nexus_core_visual(&self) -> Element<'_, Message> {
        let mission = self
            .org
            .swarm
            .as_ref()
            .and_then(|swarm| swarm.current_goal.as_deref())
            .map(|goal| trim_text(goal, 90))
            .unwrap_or_else(|| "Aguardando diretiva operacional".to_string());
        let active = role_display_name(self.active_mission_step());
        let pulse = match self.tick_counter % 4 {
            0 => "NEXUS",
            1 => "NEXUS",
            2 => "CORE",
            _ => "ONLINE",
        };
        let (ring_size, core_size, core_padding) = match self.breakpoint() {
            Breakpoint::MobileSmall | Breakpoint::MobileLarge => (238.0, 146.0, 22),
            Breakpoint::Tablet | Breakpoint::Laptop => (280.0, 166.0, 26),
            _ => (340.0, 190.0, 34),
        };

        let core = container(
            Column::new()
                .spacing(8)
                .align_items(Alignment::Center)
                .push(text(pulse).size(34).style(TEXT_PRIMARY))
                .push(text("COGNITIVE OS").size(12).style(CYAN))
                .push(text(active.to_uppercase()).size(11).style(SUCCESS)),
        )
        .padding(core_padding)
        .width(Length::Fixed(core_size))
        .height(Length::Fixed(core_size))
        .style(nexus_core_inner_style);

        let visual = container(
            Column::new()
                .align_items(Alignment::Center)
                .spacing(16)
                .push(
                    container(
                        Column::new()
                            .align_items(Alignment::Center)
                            .spacing(14)
                            .push(container(Space::new(1, 12)).width(Length::Fill))
                            .push(core)
                            .push(
                                Row::new()
                                    .spacing(10)
                                    .align_items(Alignment::Center)
                                    .push(hud_orbit_chip(
                                        "CPU",
                                        format!("{:.0}%", self.cpu_usage),
                                        ACCENT,
                                    ))
                                    .push(hud_orbit_chip(
                                        "RAM",
                                        format!("{:.0}%", self.ram_usage),
                                        WARNING,
                                    ))
                                    .push(hud_orbit_chip(
                                        "OPS",
                                        self.active_operations_count().to_string(),
                                        SUCCESS,
                                    )),
                            ),
                    )
                    .padding(28)
                    .width(Length::Fixed(ring_size))
                    .height(Length::Fixed(ring_size))
                    .style(nexus_core_ring_style),
                )
                .push(text("MISSÃO ATIVA").size(11).style(TEXT_MUTED))
                .push(text(mission).size(16).style(TEXT_PRIMARY))
                .push(text(self.current_stage.clone()).size(11).style(TEXT_MUTED)),
        )
        .padding(18)
        .width(Length::Fill)
        .height(Length::Fill)
        .style(hud_core_stage_style);

        visual.into()
    }

    fn hud_command_rail(&self) -> Element<'_, Message> {
        let mut messages = Column::new().spacing(10);
        for msg in self.messages.iter().rev().take(5).rev() {
            let is_operator = msg.role == "OPERATOR";
            messages = messages.push(
                container(
                    Column::new()
                        .spacing(5)
                        .push(
                            Row::new()
                                .spacing(8)
                                .align_items(Alignment::Center)
                                .push(
                                    text(if is_operator { "OPERATOR" } else { "NEXUS" })
                                        .size(10)
                                        .style(if is_operator { WARNING } else { CYAN }),
                                )
                                .push(text(&msg.timestamp).size(9).style(TEXT_MUTED)),
                        )
                        .push(
                            text(trim_text(&msg.content, 240))
                                .size(11)
                                .style(TEXT_PRIMARY),
                        ),
                )
                .padding(10)
                .width(Length::Fill)
                .style(if is_operator {
                    operator_bubble_modern
                } else {
                    nexus_bubble_modern
                }),
            );
        }

        if self.is_thinking {
            messages = messages.push(
                container(
                    Column::new()
                        .spacing(4)
                        .push(text("PROCESSANDO").size(10).style(CYAN))
                        .push(text(self.processing_stage()).size(11).style(TEXT_SECONDARY)),
                )
                .padding(10)
                .width(Length::Fill)
                .style(progress_bubble_modern),
            );
        }

        let mut send = button(text("SEND").size(12))
            .padding([12, 18])
            .style(theme::Button::custom(PrimaryActionButtonStyle));
        if !self.is_thinking {
            send = send.on_press(Message::Submit);
        }

        let input = container(
            Row::new()
                .spacing(8)
                .align_items(Alignment::Center)
                .push(
                    text_input("Diretiva para o NEXUS...", &self.input_value)
                        .on_input(Message::InputChanged)
                        .on_submit(Message::Submit)
                        .padding(12)
                        .width(Length::Fill),
                )
                .push(send),
        )
        .padding(8)
        .style(input_field_style);

        container(
            Column::new()
                .spacing(12)
                .push(
                    Row::new()
                        .align_items(Alignment::Center)
                        .push(text("COMMAND LINK").size(13).style(CYAN))
                        .push(Space::with_width(Length::Fill))
                        .push(
                            text(if self.is_thinking { "BUSY" } else { "READY" })
                                .size(10)
                                .style(if self.is_thinking { WARNING } else { SUCCESS }),
                        ),
                )
                .push(
                    scrollable(messages)
                        .height(Length::Fixed(
                            if self.breakpoint() == Breakpoint::Ultrawide {
                                410.0
                            } else {
                                310.0
                            },
                        ))
                        .id(scrollable::Id::new(SCROLLABLE_ID)),
                )
                .push(input)
                .push(prompt_mode_row()),
        )
        .padding(14)
        .width(Length::Fill)
        .style(hud_panel_style)
        .into()
    }

    fn conversation_helper_panel(&self) -> Element<'_, Message> {
        let last_feedback = self
            .messages
            .iter()
            .rev()
            .find_map(|msg| msg.feedback.as_ref());
        let feedback_status = last_feedback
            .map(|feedback| format!("{} · {}", feedback.intent_label, feedback.status_label))
            .unwrap_or_else(|| "Aguardando seu primeiro pedido".to_string());
        let feedback_hint = last_feedback
            .map(|feedback| feedback.user_hint.clone())
            .unwrap_or_else(|| {
                "Peça algo em linguagem natural. O NEXUS separa análise, ação real e evidência."
                    .to_string()
            });

        let mut evidence = Column::new().spacing(5);
        if let Some(feedback) = last_feedback {
            for item in feedback.evidence.iter().take(3) {
                evidence = evidence.push(
                    text(format!("• {}", trim_text(item, 72)))
                        .size(10)
                        .style(TEXT_MUTED),
                );
            }
        } else {
            evidence = evidence
                .push(
                    text("• Sem execução assumida automaticamente.")
                        .size(10)
                        .style(TEXT_MUTED),
                )
                .push(
                    text("• Mudanças aparecem em evidência ou aprovação.")
                        .size(10)
                        .style(TEXT_MUTED),
                );
        }

        container(
            Column::new()
                .spacing(12)
                .push(text("Assistente operacional").size(14).style(TEXT_PRIMARY))
                .push(
                    text("Use como você usaria o Codex: peça, acompanhe, confira.")
                        .size(11)
                        .style(TEXT_SECONDARY),
                )
                .push(
                    container(
                        Column::new()
                            .spacing(5)
                            .push(text("Último feedback").size(10).style(TEXT_MUTED))
                            .push(text(feedback_status).size(12).style(ACCENT))
                            .push(text(feedback_hint).size(10).style(TEXT_SECONDARY)),
                    )
                    .padding(10)
                    .width(Length::Fill)
                    .style(feedback_card_style),
                )
                .push(guidance_card(
                    "Analisar",
                    "Entender erro, revisar ideia, explicar risco.",
                    ACCENT,
                ))
                .push(guidance_card(
                    "Modificar",
                    "Alterar arquivos e mostrar o que mudou.",
                    PURPLE,
                ))
                .push(guidance_card(
                    "Executar",
                    "Rodar comando, teste ou verificação com status.",
                    WARNING,
                ))
                .push(
                    container(
                        Column::new()
                            .spacing(6)
                            .push(text("Evidências").size(11).style(TEXT_PRIMARY))
                            .push(evidence),
                    )
                    .padding(10)
                    .width(Length::Fill)
                    .style(task_row_style),
                ),
        )
        .padding(14)
        .width(Length::Fill)
        .style(section_style)
        .into()
    }

    fn home_hero(&self) -> Element<'_, Message> {
        let daemon = self
            .product
            .as_ref()
            .map(|item| friendly_status(&item.daemon.status))
            .unwrap_or_else(|| "iniciando".to_string());
        let local = self
            .product
            .as_ref()
            .and_then(|item| item.models.local.selected_model.as_deref())
            .unwrap_or("IA local aguardando");
        container(
            Column::new()
                .spacing(16)
                .push(text("NEXUS Cognitive OS").size(30).style(TEXT_PRIMARY))
                .push(
                    text("Uma inteligência operacional híbrida para organizar, executar, verificar e proteger ações no Linux.")
                        .size(14)
                        .style(TEXT_SECONDARY),
                )
                .push(
                    Row::new()
                        .spacing(10)
                        .push(status_badge(&daemon))
                        .push(status_badge("hybrid"))
                        .push(text(format!("Local AI: {}", trim_text(local, 24))).size(11).style(ACCENT)),
                )
                .push(
                    Row::new()
                        .spacing(10)
                        .push(
                            button(text("Ver missão").size(12))
                                .padding([10, 14])
                                .on_press(Message::SelectSection(SidebarSection::Missions)),
                        )
                        .push(
                            button(text("Abrir execuções").size(12))
                                .padding([10, 14])
                                .on_press(Message::SelectSection(SidebarSection::Executions)),
                        )
                        .push(
                            button(text("Ver swarm").size(12))
                                .padding([10, 14])
                                .on_press(Message::SelectSection(SidebarSection::Swarm)),
                        ),
                )
        )
        .padding(22)
        .width(Length::Fill)
        .style(hero_style)
        .into()
    }

    fn simple_status_cards(&self) -> Element<'_, Message> {
        let mission = self
            .org
            .swarm
            .as_ref()
            .and_then(|swarm| swarm.current_goal.as_deref())
            .map(|goal| trim_text(goal, 46))
            .unwrap_or_else(|| "Nenhuma missão ativa".to_string());
        let approvals = if self.org.approvals.is_empty() {
            "Nada aguardando você".to_string()
        } else {
            format!("{} pedem decisão", self.org.approvals.len())
        };
        let incidents = if self.org.incidents.is_empty() {
            "Sem incidentes ativos".to_string()
        } else {
            format!("{} precisam atenção", self.org.incidents.len())
        };
        let local = self
            .product
            .as_ref()
            .and_then(|item| item.models.local.selected_model.clone())
            .unwrap_or_else(|| "Ollama pendente".to_string());
        let cloud = self
            .product
            .as_ref()
            .map(|item| item.models.cloud.model.clone())
            .unwrap_or_else(|| "gemma4:31b-cloud".to_string());

        let row = Row::new()
            .spacing(12)
            .push(simple_card(
                "Missão",
                mission,
                "O que o NEXUS está tentando resolver.",
                ACCENT,
            ))
            .push(simple_card(
                "Aprovações",
                approvals,
                "Ações sensíveis só rodam com decisão humana.",
                WARNING,
            ))
            .push(simple_card(
                "Saúde",
                incidents,
                "Falhas aparecem resumidas, sem stacktrace.",
                SUCCESS,
            ))
            .push(simple_card(
                "IA local",
                trim_text(&local, 28),
                "Rápida, privada e offline quando possível.",
                ACCENT,
            ))
            .push(simple_card(
                "IA cloud",
                trim_text(&cloud, 28),
                "Raciocínio avançado para tarefas complexas.",
                WARNING,
            ));

        if self.breakpoint().is_mobile() {
            scrollable(row)
                .direction(scrollable::Direction::Horizontal(
                    scrollable::Properties::new().width(4),
                ))
                .height(Length::Fixed(128.0))
                .into()
        } else {
            row.into()
        }
    }

    fn conversation_panel(&self) -> Element<'_, Message> {
        let mut messages = Column::new().spacing(12);
        for msg in self.messages.iter().rev().take(8).rev() {
            let is_operator = msg.role == "OPERATOR";
            let mut message_body = Column::new()
                .spacing(8)
                .push(
                    Row::new()
                        .spacing(8)
                        .align_items(Alignment::Center)
                        .push(
                            text(if is_operator { "Você" } else { "NEXUS" })
                                .size(11)
                                .style(if is_operator { WARNING } else { ACCENT }),
                        )
                        .push(text(&msg.timestamp).size(9).style(TEXT_MUTED)),
                )
                .push(
                    text(trim_text(&msg.content, 520))
                        .size(13)
                        .style(TEXT_PRIMARY),
                );

            if let Some(feedback) = &msg.feedback {
                message_body = message_body.push(feedback_card(feedback));
            }

            let bubble = container(message_body)
                .padding(16)
                .width(Length::FillPortion(80))
                .style(if is_operator {
                    operator_bubble_modern
                } else {
                    nexus_bubble_modern
                });

            messages = messages.push(
                Row::new()
                    .width(Length::Fill)
                    .align_items(Alignment::Center)
                    .push(if is_operator {
                        Space::with_width(Length::Fill)
                    } else {
                        Space::new(0, 0)
                    })
                    .push(bubble)
                    .push(if is_operator {
                        Space::new(0, 0)
                    } else {
                        Space::with_width(Length::Fill)
                    }),
            );
        }
        if self.is_thinking {
            messages = messages.push(
                container(
                    Column::new()
                        .spacing(6)
                        .push(text("NEXUS está trabalhando").size(11).style(ACCENT))
                        .push(text(self.processing_stage()).size(12).style(TEXT_SECONDARY))
                        .push(text("Ele só deve declarar alteração real quando houver evidência ou execução registrada.").size(10).style(TEXT_MUTED)),
                )
                    .padding(10)
                    .width(Length::Fill)
                    .style(progress_bubble_modern),
            );
        }

        let mut send = button(text("Enviar").size(13))
            .padding([14, 20])
            .style(theme::Button::custom(PrimaryActionButtonStyle));
        if !self.is_thinking {
            send = send.on_press(Message::Submit);
        }

        let input_row = container(
            Row::new()
                .spacing(10)
                .align_items(Alignment::Center)
                .push(
                    text_input(
                        "Ex.: analise este erro, modifique o frontend, rode uma verificação...",
                        &self.input_value,
                    )
                    .on_input(Message::InputChanged)
                    .on_submit(Message::Submit)
                    .padding(14)
                    .width(Length::Fill),
                )
                .push(send),
        )
        .padding([12, 12])
        .style(input_field_style);

        container(
            Column::new()
                .spacing(18)
                .push(
                    Column::new()
                        .spacing(8)
                        .push(text("Converse com o NEXUS").size(22).style(TEXT_PRIMARY))
                        .push(text("Peça em linguagem natural. A resposta separa intenção, ação real, evidência e próximo passo.").size(12).style(TEXT_SECONDARY)),
                )
                .push(prompt_mode_row())
                .push(
                    container(
                        scrollable(messages)
                            .height(Length::Fill)
                            .id(scrollable::Id::new(SCROLLABLE_ID)),
                    )
                        .height(Length::Fill)
                        .style(section_style)
                )
                .push(input_row),
        )
        .padding(20)
        .width(Length::Fill)
        .height(Length::Fill)
        .style(section_style)
        .into()
    }

    fn latest_events_simple(&self) -> Element<'_, Message> {
        let mut col = Column::new()
            .spacing(10)
            .push(text("O que aconteceu agora").size(13).style(TEXT_PRIMARY));
        for item in self.visible_activity().iter().rev().take(4) {
            col = col.push(
                container(
                    Column::new()
                        .spacing(3)
                        .push(text(&item.label).size(12).style(TEXT_PRIMARY))
                        .push(
                            text(trim_text(&item.detail, 100))
                                .size(10)
                                .style(TEXT_MUTED),
                        ),
                )
                .padding(10)
                .width(Length::Fill)
                .style(task_row_style),
            );
        }
        container(col)
            .padding(14)
            .width(Length::Fill)
            .style(section_style)
            .into()
    }

    fn missions_page(&self) -> Element<'_, Message> {
        let mission = self
            .org
            .swarm
            .as_ref()
            .and_then(|swarm| swarm.current_goal.as_deref())
            .map(|goal| trim_text(goal, 96))
            .unwrap_or_else(|| "Nenhuma tarefa ativa no momento.".to_string());

        let mut tasks = Column::new().spacing(12);
        if let Some(swarm) = &self.org.swarm {
            for item in swarm.plan.iter().take(6) {
                tasks = tasks.push(premium_task_item(
                    item.task.clone(),
                    friendly_task_status(&item.status),
                    format!("Responsável: {}", role_display_name(&item.role)),
                ));
            }
        }

        if self
            .org
            .swarm
            .as_ref()
            .map(|swarm| swarm.plan.is_empty())
            .unwrap_or(true)
        {
            tasks = tasks
                .push(premium_task_item(
                    "Criar um plano de ação",
                    "Pronto para começar",
                    "Peça ao NEXUS para transformar uma ideia em passos claros.",
                ))
                .push(premium_task_item(
                    "Organizar prioridades",
                    "Sugestão",
                    "Use a conversa para priorizar arquivos, decisões ou próximos passos.",
                ))
                .push(premium_task_item(
                    "Resumir o projeto",
                    "Sugestão",
                    "O NEXUS pode gerar uma visão clara antes de executar qualquer ação.",
                ));
        }

        self.premium_page_shell(
            "Tarefas",
            "Acompanhe o que importa sem ruído técnico.",
            Column::new()
                .spacing(16)
                .push(
                    container(
                        Column::new()
                            .spacing(8)
                            .push(text("Foco atual").size(13).style(CYAN))
                            .push(text(mission).size(22).style(TEXT_PRIMARY))
                            .push(
                                text("Tudo que exige detalhes técnicos fica disponível apenas no modo desenvolvedor.")
                                    .size(13)
                                    .style(TEXT_SECONDARY),
                            ),
                    )
                    .padding(22)
                    .width(Length::Fill)
                    .style(premium_surface_style),
                )
                .push(tasks),
        )
    }

    fn swarm_page(&self) -> Element<'_, Message> {
        scrollable(
            Column::new()
                .spacing(14)
                .push(page_header(
                    "Swarm",
                    "Quem esta atuando e como a missao flui entre agentes.",
                ))
                .push(self.role_summary_row(
                    "CEO",
                    "Mostra se a empresa cognitiva esta coordenada.",
                    "CTO",
                    "Mostra qual agente assumiu cada parte da operacao.",
                    "Usuario",
                    "Mostra quem esta cuidando da tarefa em linguagem simples.",
                ))
                .push(self.mission_flow_visualization())
                .push(self.cognitive_team_panel()),
        )
        .height(Length::Fill)
        .into()
    }

    fn executions_page(&self) -> Element<'_, Message> {
        scrollable(
            Column::new()
                .spacing(14)
                .push(page_header(
                    "Execuções",
                    "Acoes reais executadas com resultado e verificacao.",
                ))
                .push(self.role_summary_row(
                    "CEO",
                    "Confirma se houve resultado real antes de considerar concluido.",
                    "CTO",
                    "Valida status, verificacao e evidencia tecnica quando necessario.",
                    "Usuario",
                    "Entende o que foi feito e se deu certo.",
                ))
                .push(container(self.execution_panel()).style(section_style)),
        )
        .height(Length::Fill)
        .into()
    }

    fn approvals_page(&self) -> Element<'_, Message> {
        scrollable(
            Column::new()
                .spacing(14)
                .push(page_header(
                    "Aprovações",
                    "Comandos sensiveis aguardando decisao humana.",
                ))
                .push(self.role_summary_row(
                    "CEO",
                    "Decide se o impacto de negocio e aceitavel.",
                    "CTO",
                    "Revisa comando, rollback e risco operacional.",
                    "Usuario",
                    "Aprova apenas quando entende a consequencia.",
                ))
                .push(section_block("PENDENTES", self.approval_queue_column(true)))
                .push(section_block(
                    "PRONTAS PARA EXECUTAR",
                    self.approval_queue_column(false),
                )),
        )
        .height(Length::Fill)
        .into()
    }

    fn incidents_page(&self) -> Element<'_, Message> {
        scrollable(
            Column::new()
                .spacing(14)
                .push(page_header(
                    "Incidentes",
                    "Falhas, bloqueios e alertas em linguagem resumida.",
                ))
                .push(self.role_summary_row(
                    "CEO",
                    "Ve impacto e severidade sem stacktrace.",
                    "CTO",
                    "Investiga modulo, agente e rollback em modo engenharia.",
                    "Usuario",
                    "Sabe se precisa parar, aguardar ou pedir ajuda.",
                ))
                .push(
                    container(self.incident_center_content())
                        .padding(14)
                        .style(section_style),
                ),
        )
        .height(Length::Fill)
        .into()
    }

    fn observer_page(&self) -> Element<'_, Message> {
        scrollable(
            Column::new()
                .spacing(14)
                .push(page_header(
                    "Observador",
                    "Contexto do Linux que ajuda o NEXUS a entender o ambiente.",
                ))
                .push(self.role_summary_row(
                    "CEO",
                    "Entende o modo operacional atual da equipe/sistema.",
                    "CTO",
                    "Confere foco, Git, containers e pressao de recurso.",
                    "Usuario",
                    "Ve se o NEXUS percebe o ambiente corretamente.",
                ))
                .push(
                    container(self.observer_content())
                        .padding(14)
                        .style(section_style),
                ),
        )
        .height(Length::Fill)
        .into()
    }

    fn telemetry_page(&self) -> Element<'_, Message> {
        scrollable(
            Column::new()
                .spacing(14)
                .push(page_header(
                    "Telemetria",
                    "Sinais cognitivos essenciais, sem ruído técnico.",
                ))
                .push(self.role_summary_row(
                    "CEO",
                    "Le saude operacional em quatro sinais.",
                    "CTO",
                    "Acompanha pressao de agentes, runtime e memoria.",
                    "Usuario",
                    "Entende se o sistema esta leve ou sobrecarregado.",
                ))
                .push(self.cognitive_telemetry_panel()),
        )
        .height(Length::Fill)
        .into()
    }

    fn memory_page(&self) -> Element<'_, Message> {
        scrollable(
            Column::new()
                .spacing(14)
                .push(page_header(
                    "Memória",
                    "Decisoes, aprendizados e registros organizacionais.",
                ))
                .push(self.role_summary_row(
                    "CEO",
                    "Ve aprendizado e rastreabilidade de decisoes.",
                    "CTO",
                    "Confere eventos, verificacoes e historico persistido.",
                    "Usuario",
                    "Entende o que o NEXUS esta lembrando.",
                ))
                .push(
                    container(self.memory_content())
                        .padding(14)
                        .style(section_style),
                ),
        )
        .height(Length::Fill)
        .into()
    }

    fn settings_page(&self) -> Element<'_, Message> {
        let mut settings = Column::new()
            .spacing(12)
            .push(settings_item(
                "Experiência",
                "Interface conversacional limpa",
                "Ativo",
                SUCCESS,
            ))
            .push(settings_item(
                "Anexos e voz",
                "Entrada pronta para arquivos e comandos por voz",
                "Disponível",
                CYAN,
            ))
            .push(settings_item(
                "Privacidade",
                "Ações sensíveis continuam exigindo confirmação",
                "Protegido",
                SUCCESS,
            ))
            .push(
                container(
                    Row::new()
                        .spacing(14)
                        .align_items(Alignment::Center)
                        .push(
                            Column::new()
                                .spacing(5)
                                .push(text("Modo desenvolvedor").size(15).style(TEXT_PRIMARY))
                                .push(
                                    text("Mostra detalhes internos somente quando você quiser.")
                                        .size(13)
                                        .style(TEXT_SECONDARY),
                                ),
                        )
                        .push(Space::with_width(Length::Fill))
                        .push(
                            Toggler::new(None, self.engineering_mode, |_| {
                                Message::ToggleEngineeringMode
                            })
                            .size(26)
                            .width(Length::Shrink)
                            .style(theme::Toggler::Custom(Box::new(PremiumTogglerStyle))),
                        ),
                )
                .padding(18)
                .width(Length::Fill)
                .style(premium_surface_style),
            );

        if self.engineering_mode {
            settings = settings.push(
                container(
                    Column::new()
                        .spacing(14)
                        .push(text("Detalhes de engenharia").size(16).style(TEXT_PRIMARY))
                        .push(text("Área opcional para diagnóstico. A experiência principal permanece limpa.").size(13).style(TEXT_MUTED))
                        .push(self.product_overview_strip())
                        .push(self.product_status_panel()),
                )
                .padding(18)
                .width(Length::Fill)
                .style(premium_surface_style),
            );
        }

        self.premium_page_shell(
            "Configurações",
            "Preferências simples para manter o NEXUS silencioso e focado.",
            settings,
        )
    }

    fn premium_page_shell<'a>(
        &self,
        title: &'static str,
        subtitle: &'static str,
        body: Column<'a, Message>,
    ) -> Element<'a, Message> {
        let page_width = if self.breakpoint().is_tablet_or_smaller() {
            Length::Fill
        } else {
            Length::Fixed(860.0)
        };

        container(
            scrollable(
                Column::new()
                    .spacing(24)
                    .align_items(Alignment::Center)
                    .push(Space::with_height(Length::Fixed(
                        if self.breakpoint().is_mobile() {
                            10.0
                        } else {
                            34.0
                        },
                    )))
                    .push(
                        Column::new()
                            .spacing(8)
                            .align_items(Alignment::Center)
                            .push(text(title).size(32).style(TEXT_PRIMARY))
                            .push(text(subtitle).size(15).style(TEXT_SECONDARY)),
                    )
                    .push(container(body).width(page_width)),
            )
            .height(Length::Fill),
        )
        .width(Length::Fill)
        .height(Length::Fill)
        .style(chat_workspace_style)
        .into()
    }

    fn role_summary_row(
        &self,
        label_a: &'static str,
        text_a: &'static str,
        label_b: &'static str,
        text_b: &'static str,
        label_c: &'static str,
        text_c: &'static str,
    ) -> Element<'_, Message> {
        let row = Row::new()
            .spacing(10)
            .push(role_summary_card(label_a, text_a, ACCENT))
            .push(role_summary_card(label_b, text_b, WARNING))
            .push(role_summary_card(label_c, text_c, SUCCESS));
        if self.breakpoint().is_mobile() {
            scrollable(row)
                .direction(scrollable::Direction::Horizontal(
                    scrollable::Properties::new().width(4),
                ))
                .height(Length::Fixed(98.0))
                .into()
        } else {
            row.into()
        }
    }

    fn operator_console(&self) -> Element<'_, Message> {
        let mission = self
            .org
            .swarm
            .as_ref()
            .and_then(|swarm| swarm.current_goal.as_deref())
            .unwrap_or("No active mission loaded from organizational runtime.");

        let mut response_col = Column::new().spacing(12);

        for msg in self.messages.iter().rev().take(4).rev() {
            let is_operator = msg.role == "OPERATOR";
            response_col = response_col.push(
                Column::new()
                    .spacing(4)
                    .push(
                        text(format!("{} · {}", msg.role, msg.timestamp))
                            .size(10)
                            .style(if is_operator { WARNING } else { ACCENT }),
                    )
                    .push(
                        container(
                            text(trim_text(&msg.content, 420))
                                .size(12)
                                .style(TEXT_PRIMARY),
                        )
                        .padding(12)
                        .width(Length::Fill)
                        .style(if is_operator {
                            chat_msg_user_style
                        } else if msg.role == "TERMINAL" {
                            chat_msg_terminal_style
                        } else if msg.role == "EVIDENCE" {
                            chat_msg_evidence_style
                        } else {
                            chat_msg_nexus_style
                        }),
                    ),
            );
        }

        if self.is_thinking {
            response_col = response_col.push(
                container(text(self.processing_stage()).size(12).style(ACCENT))
                    .padding(10)
                    .width(Length::Fill)
                    .style(progress_bubble_modern),
            );
        }

        let mut approval_col = Column::new().spacing(8);
        for approval in self.org.approvals.iter().take(3) {
            let proposal_id = approval_proposal_id(approval);
            approval_col = approval_col.push(
                button(
                    Column::new()
                        .spacing(3)
                        .push(text(trim_text(&approval.command, 56)).size(11))
                        .push(
                            text(format!(
                                "{} · {}",
                                approval.risk,
                                trim_text(&approval_impact_line(approval), 44)
                            ))
                            .size(10),
                        ),
                )
                .padding(8)
                .width(Length::Fill)
                .on_press(Message::SelectPendingApproval(proposal_id)),
            );
        }
        if self.org.approvals.is_empty() {
            approval_col = approval_col.push(
                text("No approval requests in queue.")
                    .size(11)
                    .style(TEXT_MUTED),
            );
        }
        if let Some(approval) = self.selected_pending_approval() {
            approval_col = approval_col.push(self.approval_detail_card(
                "SELECTED APPROVAL",
                approval,
                Some(Message::ApproveSelected),
                "APPROVE ONCE",
            ));
        }

        let mut execution_col = Column::new().spacing(8);
        for approval in self.org.approved_commands.iter().take(2) {
            let proposal_id = approval_proposal_id(approval);
            execution_col = execution_col.push(
                button(
                    Column::new()
                        .spacing(3)
                        .push(text(trim_text(&approval.command, 56)).size(11))
                        .push(text(format!("approved · {}", approval.risk)).size(10)),
                )
                .padding(8)
                .width(Length::Fill)
                .on_press(Message::SelectApprovedCommand(proposal_id)),
            );
        }
        if self.org.approved_commands.is_empty() {
            execution_col = execution_col.push(
                text("No approved command waiting for execution.")
                    .size(11)
                    .style(TEXT_MUTED),
            );
        }
        if let Some(approval) = self.selected_approved_command() {
            execution_col = execution_col.push(self.approval_detail_card(
                "READY FOR RUNTIME",
                approval,
                Some(Message::ExecuteSelected),
                "EXECUTE",
            ));
        }

        let input = Row::new()
            .spacing(10)
            .align_items(Alignment::Center)
            .push(
                text_input("OPERATOR DIRECTIVE...", &self.input_value)
                    .on_input(Message::InputChanged)
                    .on_submit(Message::Submit)
                    .padding(12),
            )
            .push({
                let mut btn = button(text("SEND").size(12)).padding([10, 16]);
                if !self.is_thinking {
                    btn = btn.on_press(Message::Submit);
                }
                btn
            });

        scrollable(
            Column::new()
                .spacing(18)
                .padding(20)
                .push(
                    text("OPERATOR COMMAND CONSOLE")
                        .size(13)
                        .style(TEXT_PRIMARY),
                )
                .push(section_block(
                    "ACTIVE MISSION",
                    Column::new()
                        .spacing(6)
                        .push(text(trim_text(mission, 180)).size(12).style(TEXT_PRIMARY))
                        .push(
                            text(format!("Stage: {}", self.current_stage))
                                .size(11)
                                .style(TEXT_MUTED),
                        ),
                ))
                .push(section_block("DIRECTIVE INPUT", Column::new().push(input)))
                .push(section_block("APPROVAL QUEUE", approval_col))
                .push(section_block("EXECUTION FEEDBACK", execution_col))
                .push(section_block("STRUCTURED RESPONSES", response_col)),
        )
        .id(scrollable::Id::new(SCROLLABLE_ID))
        .height(Length::Fill)
        .into()
    }

    fn approval_queue_column(&self, pending: bool) -> Column<'_, Message> {
        let items = if pending {
            &self.org.approvals
        } else {
            &self.org.approved_commands
        };
        let mut col = Column::new().spacing(10);
        for approval in items
            .iter()
            .take(if self.engineering_mode { 10 } else { 5 })
        {
            let proposal_id = approval_proposal_id(approval);
            let action = if pending {
                Message::SelectPendingApproval(proposal_id)
            } else {
                Message::SelectApprovedCommand(proposal_id)
            };
            col = col.push(
                button(
                    Column::new()
                        .spacing(4)
                        .push(text(human_command_label(&approval.command)).size(12))
                        .push(
                            text(format!(
                                "{} · {}",
                                friendly_risk(&approval.risk),
                                approval_impact_line(approval)
                            ))
                            .size(10),
                        ),
                )
                .padding(10)
                .width(Length::Fill)
                .on_press(action),
            );
        }
        if items.is_empty() {
            col = col.push(
                text(if pending {
                    "Nenhuma aprovacao pendente."
                } else {
                    "Nenhum comando aprovado aguardando execucao."
                })
                .size(11)
                .style(TEXT_MUTED),
            );
        }
        if pending {
            if let Some(approval) = self.selected_pending_approval() {
                col = col.push(self.approval_detail_card(
                    "APROVACAO SELECIONADA",
                    approval,
                    Some(Message::ApproveSelected),
                    "APROVAR UMA VEZ",
                ));
            }
        } else if let Some(approval) = self.selected_approved_command() {
            col = col.push(self.approval_detail_card(
                "PRONTA PARA EXECUTAR",
                approval,
                Some(Message::ExecuteSelected),
                "EXECUTAR",
            ));
        }
        col
    }

    fn operations_center(&self) -> Element<'_, Message> {
        let runtime_and_tasks: Element<'_, Message> = if self.breakpoint().is_tablet_or_smaller() {
            Column::new()
                .spacing(12)
                .push(self.mission_command_overview())
                .push(container(self.execution_panel()).style(section_style))
                .push(container(self.mission_progress_panel()).style(section_style))
                .into()
        } else {
            Row::new()
                .spacing(14)
                .push(
                    container(self.mission_command_overview())
                        .width(Length::FillPortion(2))
                        .style(section_style),
                )
                .push(
                    container(self.execution_panel())
                        .width(Length::FillPortion(
                            if self.breakpoint() == Breakpoint::Ultrawide {
                                4
                            } else {
                                3
                            },
                        ))
                        .style(section_style),
                )
                .push(
                    container(self.mission_progress_panel())
                        .width(Length::FillPortion(2))
                        .style(section_style),
                )
                .into()
        };

        Column::new()
            .spacing(14)
            .padding(self.panel_padding())
            .push(self.product_overview_strip())
            .push(self.mission_flow_visualization())
            .push(runtime_and_tasks)
            .push(self.cognitive_team_panel())
            .into()
    }

    fn product_overview_strip(&self) -> Element<'_, Message> {
        let product = self.product.as_ref();
        let daemon = product
            .map(|item| friendly_status(&item.daemon.status))
            .unwrap_or_else(|| "carregando".to_string());
        let local = product
            .and_then(|item| item.models.local.selected_model.as_deref())
            .unwrap_or("Ollama aguardando");
        let cloud = product
            .map(|item| {
                if item.models.cloud.ready {
                    format!("{} {}", item.models.cloud.provider, item.models.cloud.model)
                } else {
                    format!("{} sem chave", item.models.cloud.provider)
                }
            })
            .unwrap_or_else(|| "cloud pendente".to_string());
        let install = product
            .map(|item| {
                if item.paths.project_root == "/usr/lib/nexus" {
                    "pacote .deb ativo".to_string()
                } else {
                    "modo workspace".to_string()
                }
            })
            .unwrap_or_else(|| "detectando install".to_string());

        let row = Row::new()
            .spacing(10)
            .push(overview_chip("Sistema", daemon, SUCCESS))
            .push(overview_chip("LLM local", trim_text(local, 22), ACCENT))
            .push(overview_chip("LLM cloud", cloud, WARNING))
            .push(overview_chip("Instalacao", install, TEXT_SECONDARY));

        let chips: Element<'_, Message> = if self.breakpoint().is_mobile() {
            scrollable(row)
                .direction(scrollable::Direction::Horizontal(
                    scrollable::Properties::new().width(4),
                ))
                .height(Length::Fixed(66.0))
                .into()
        } else {
            row.into()
        };

        container(
            Column::new()
                .spacing(8)
                .push(
                    Row::new()
                        .push(text("PLATAFORMA").size(12).style(TEXT_SECONDARY))
                        .push(Space::with_width(Length::Fill))
                        .push(
                            text(
                                product
                                    .map(|item| item.autonomy_level.as_str())
                                    .unwrap_or("GUARDED"),
                            )
                            .size(11)
                            .style(ACCENT),
                        ),
                )
                .push(chips),
        )
        .padding(14)
        .style(platform_strip_style)
        .into()
    }

    fn mission_command_overview(&self) -> Element<'_, Message> {
        let goal = self
            .org
            .swarm
            .as_ref()
            .and_then(|swarm| swarm.current_goal.as_deref())
            .map(|goal| trim_text(goal, 130))
            .unwrap_or_else(|| "Aguardando uma missao real do operador.".to_string());
        let daemon_line = self
            .product
            .as_ref()
            .map(|status| {
                format!(
                    "{} · {} agentes · PID {}",
                    friendly_status(&status.daemon.status),
                    status.daemon.agents,
                    status
                        .daemon
                        .pid
                        .map(|pid| pid.to_string())
                        .unwrap_or_else(|| "n/a".to_string())
                )
            })
            .unwrap_or_else(|| "Status do produto ainda nao carregado.".to_string());
        let decision = self.active_mission_step();
        let evidence = self
            .latest_verification()
            .map(|item| verification_evidence_line(item))
            .unwrap_or_else(|| "Nenhuma evidencia de verificacao registrada ainda.".to_string());

        Column::new()
            .spacing(12)
            .push(text("CENTRO DA MISSAO").size(13).style(TEXT_PRIMARY))
            .push(summary_banner(
                goal,
                format!("Agora: {} · {}", role_display_name(decision), daemon_line),
                status_color(
                    self.product
                        .as_ref()
                        .map(|status| status.daemon.status.as_str())
                        .unwrap_or("ready"),
                ),
            ))
            .push(runtime_line(
                "Decisao",
                role_action_label(decision),
                TEXT_SECONDARY,
            ))
            .push(runtime_line(
                "Aprovações",
                &format!("{} aguardando", self.org.approvals.len()),
                if self.org.approvals.is_empty() {
                    SUCCESS
                } else {
                    WARNING
                },
            ))
            .push(runtime_line(
                "Evidencia",
                &trim_text(&evidence, 80),
                TEXT_SECONDARY,
            ))
            .push(runtime_line(
                "Roteamento",
                &self.hybrid_routing_line(),
                ACCENT,
            ))
            .into()
    }

    fn mission_flow_visualization(&self) -> Element<'_, Message> {
        let roles = ["planner", "devops", "reviewer", "security", "runtime"];
        let mut row = Row::new().spacing(8).align_items(Alignment::Center);
        let active_step = self.active_mission_step();

        for (idx, role) in roles.iter().enumerate() {
            let agent = self.find_agent(role);
            let status = agent
                .map(|item| item.status.as_str())
                .unwrap_or(if *role == "runtime" {
                    "ready"
                } else {
                    "offline"
                });
            let task_line = agent
                .and_then(|item| item.current_task.as_deref())
                .map(|task| short_id(task))
                .unwrap_or_else(|| next_action_for_role(role, self).to_string());
            let is_active = active_step == *role;
            row = row.push(
                container(
                    Column::new()
                        .spacing(5)
                        .align_items(Alignment::Center)
                        .push(
                            text(role_display_name(role).to_uppercase())
                                .size(11)
                                .style(if is_active { SUCCESS } else { TEXT_PRIMARY }),
                        )
                        .push(status_badge(if is_active { "active" } else { status }))
                        .push(text(role_action_label(role)).size(10).style(TEXT_SECONDARY))
                        .push(text(task_line).size(9).style(TEXT_MUTED)),
                )
                .padding([10, 12])
                .width(if self.breakpoint().is_mobile() {
                    Length::Fixed(132.0)
                } else {
                    Length::FillPortion(1)
                })
                .style(if is_active {
                    active_flow_node_style
                } else {
                    flow_node_style
                }),
            );
            if idx < roles.len() - 1 {
                row = row.push(icon(
                    NexusIcon::ChevronRight,
                    16,
                    if is_active { SUCCESS } else { ACCENT },
                ));
            }
        }

        container(
            Column::new()
                .spacing(10)
                .push(
                    Row::new()
                        .push(text("FLUXO DA MISSAO").size(13).style(TEXT_PRIMARY))
                        .push(Space::with_width(Length::Fill))
                        .push(text(self.mission_status_line()).size(11).style(TEXT_MUTED)),
                )
                .push(if self.breakpoint().is_mobile() {
                    let flow: Element<'_, Message> = scrollable(row)
                        .direction(scrollable::Direction::Horizontal(
                            scrollable::Properties::new().width(4),
                        ))
                        .height(Length::Fixed(92.0))
                        .into();
                    flow
                } else {
                    let flow: Element<'_, Message> = row.into();
                    flow
                }),
        )
        .padding(14)
        .style(section_style)
        .into()
    }

    fn cognitive_team_panel(&self) -> Element<'_, Message> {
        let agents_grid = self.agent_grid();

        container(
            Column::new()
                .spacing(12)
                .push(text("EQUIPE COGNITIVA").size(13).style(TEXT_PRIMARY))
                .push(
                    text("Quem esta cuidando da missao agora, em linguagem operacional.")
                        .size(10)
                        .style(TEXT_MUTED),
                )
                .push(scrollable(agents_grid).height(Length::Fill)),
        )
        .padding(14)
        .height(Length::Fill)
        .style(section_style)
        .into()
    }

    fn agent_grid(&self) -> Element<'_, Message> {
        let Some(swarm) = &self.org.swarm else {
            return empty_state("No active agents loaded.", "Waiting for real Swarm state.");
        };
        if swarm.agents.is_empty() {
            return empty_state(
                "No active agents loaded.",
                "Agent registry has no persisted state.",
            );
        }

        let columns_count = match self.breakpoint() {
            Breakpoint::MobileSmall | Breakpoint::MobileLarge => 1,
            Breakpoint::Tablet | Breakpoint::Laptop | Breakpoint::Desktop => 2,
            Breakpoint::Ultrawide => 3,
        };
        let mut columns: Vec<Column<'_, Message>> = (0..columns_count)
            .map(|_| Column::new().spacing(10).width(Length::Fill))
            .collect();
        for (i, agent) in swarm.agents.iter().enumerate() {
            let idx = i % columns_count;
            let current = std::mem::replace(
                &mut columns[idx],
                Column::new().spacing(10).width(Length::Fill),
            );
            columns[idx] = current.push(self.agent_card(agent));
        }
        let mut row = Row::new().spacing(12);
        for column in columns {
            row = row.push(column);
        }
        row.into()
    }

    fn execution_panel(&self) -> Element<'_, Message> {
        let active_command = self.org.commands.first();
        let mut stream = Column::new().spacing(8);

        if let Some(command) = active_command {
            let verification = self.latest_verification();
            let stdout_tail = verification
                .and_then(|item| item.evidence.get("stdout_tail"))
                .and_then(|value| value.as_str())
                .unwrap_or("")
                .trim();
            let stderr_tail = verification
                .and_then(|item| item.evidence.get("stderr_tail"))
                .and_then(|value| value.as_str())
                .unwrap_or("")
                .trim();
            stream = stream
                .push(summary_banner(
                    execution_summary(command, self.latest_verification()),
                    execution_result_label(command, self.latest_verification()),
                    status_color(&command.status),
                ))
                .push(runtime_line(
                    "Acao",
                    &human_command_label(&command.command),
                    TEXT_PRIMARY,
                ))
                .push(runtime_line(
                    "Resultado",
                    &friendly_status(&command.status),
                    status_color(&command.status),
                ))
                .push(runtime_line(
                    "Evidencia",
                    self.latest_verification_status().as_str(),
                    status_color(self.latest_verification_status().as_str()),
                ))
                .push(runtime_line(
                    "Duracao",
                    &command
                        .duration_ms
                        .map(|ms| format!("{}ms", ms))
                        .unwrap_or_else(|| "em andamento ou nao capturada".to_string()),
                    TEXT_SECONDARY,
                ))
                .push(runtime_line(
                    "Detalhes",
                    &command
                        .pid
                        .map(|pid| format!("PID {}", pid))
                        .unwrap_or_else(|| "PID nao capturado".to_string()),
                    TEXT_SECONDARY,
                ))
                .push(runtime_line(
                    "Codigo",
                    &command
                        .exit_code
                        .map(|code| code.to_string())
                        .unwrap_or_else(|| "nao capturado".to_string()),
                    if command.exit_code == Some(0) {
                        SUCCESS
                    } else if command.exit_code.is_some() {
                        DANGER
                    } else {
                        TEXT_MUTED
                    },
                ))
                .push(runtime_line(
                    "Reversao",
                    self.rollback_hint(command).as_str(),
                    WARNING,
                ));
            if self.engineering_mode {
                stream = stream
                    .push(log_block("Saida normal", stdout_tail, SUCCESS))
                    .push(log_block("Alertas / erro", stderr_tail, DANGER))
                    .push(technical_detail_block(command));
            }
        } else {
            stream = stream.push(empty_state(
                "Nenhuma execucao registrada.",
                "A execucao aparece aqui quando um comando aprovado roda de verdade.",
            ));
        }

        if self.engineering_mode {
            for event in self.org.runtime_events.iter().take(5) {
                let detail = runtime_event_detail(event);
                stream = stream.push(runtime_line(
                    &event.event_type,
                    &trim_text(&detail, 96),
                    if event.event_type.contains("FAILED") {
                        DANGER
                    } else {
                        TEXT_SECONDARY
                    },
                ));
            }
        }

        Column::new()
            .spacing(10)
            .push(
                Row::new()
                    .spacing(8)
                    .align_items(Alignment::Center)
                    .push(text("EXECUCAO").size(13).style(TEXT_PRIMARY))
                    .push(Space::with_width(Length::Fill))
                    .push(
                        button(text("COPY CMD").size(10))
                            .padding([6, 10])
                            .on_press(Message::CopyCurrentCommand),
                    )
                    .push(
                        button(text("COPY LOGS").size(10))
                            .padding([6, 10])
                            .on_press(Message::CopyRuntimeLogs),
                    )
                    .push(status_badge(
                        active_command
                            .map(|command| command.status.as_str())
                            .unwrap_or("idle"),
                    )),
            )
            .push(
                self.copied_feedback
                    .as_deref()
                    .map(|feedback| text(feedback).size(10).style(SUCCESS))
                    .unwrap_or_else(|| {
                        text(if self.engineering_mode {
                            "modo engenharia: evidencias e detalhes tecnicos visiveis"
                        } else {
                            "modo publico: resumo claro de execucoes reais"
                        })
                        .size(10)
                        .style(TEXT_MUTED)
                    }),
            )
            .push(scrollable(stream).height(Length::Fixed(self.command_stream_height())))
            .into()
    }

    fn mission_progress_panel(&self) -> Element<'_, Message> {
        let mut col = Column::new().spacing(8);
        let mut has_tasks = false;
        if let Some(swarm) = &self.org.swarm {
            for task in swarm.tasks.iter().take(7) {
                has_tasks = true;
                let lifecycle = lifecycle_state(task);
                col = col.push(
                    container(
                        Column::new()
                            .spacing(4)
                            .push(
                                Row::new()
                                    .align_items(Alignment::Center)
                                    .push(status_badge(&friendly_lifecycle(&lifecycle)))
                                    .push(Space::with_width(Length::Fill))
                                    .push(text(timestamp_for_task(task)).size(9).style(TEXT_MUTED)),
                            )
                            .push(
                                text(trim_text(&human_task_title(task), 58))
                                    .size(11)
                                    .style(TEXT_PRIMARY),
                            )
                            .push(
                                text(format!("responsavel: {}", role_display_name(&task.owner)))
                                    .size(10)
                                    .style(TEXT_MUTED),
                            )
                            .push(if self.engineering_mode {
                                Row::new()
                                    .spacing(10)
                                    .push(
                                        text(format!("prioridade {}", task_priority(task)))
                                            .size(10)
                                            .style(TEXT_MUTED),
                                    )
                                    .push(
                                        text(format!("risco {}", friendly_risk(&task_risk(task))))
                                            .size(10)
                                            .style(risk_color(&task_risk(task))),
                                    )
                                    .push(
                                        text(format!("progresso {}", task_progress(&lifecycle)))
                                            .size(10)
                                            .style(ACCENT),
                                    )
                            } else {
                                Row::new().spacing(10).push(
                                    text(format!("progresso {}", task_progress(&lifecycle)))
                                        .size(10)
                                        .style(ACCENT),
                                )
                            })
                            .push(
                                text(format!("proximo passo: {}", task_last_action(task)))
                                    .size(10)
                                    .style(TEXT_SECONDARY),
                            ),
                    )
                    .padding(8)
                    .width(Length::Fill)
                    .style(task_row_style),
                );
            }
        }
        if !has_tasks {
            col = col.push(
                text("Nenhuma etapa de missao carregada.")
                    .size(11)
                    .style(TEXT_MUTED),
            );
        }

        Column::new()
            .spacing(10)
            .push(text("PROGRESSO DA MISSAO").size(13).style(TEXT_PRIMARY))
            .push(scrollable(col).height(Length::Fixed(self.task_panel_height())))
            .into()
    }

    fn agent_card(&self, agent: &SwarmAgent) -> Element<'_, Message> {
        let heartbeat_age = trim_text(&agent.last_heartbeat, 19);
        let latency = if agent.status == "idle" {
            "aguardando"
        } else {
            "ativo"
        };
        let current_task = agent
            .current_task
            .as_deref()
            .map(|task| {
                if self.engineering_mode {
                    short_id(task)
                } else {
                    trim_text(task, 54)
                }
            })
            .unwrap_or_else(|| "sem tarefa ativa".to_string());
        let action = self
            .org
            .agent_ticks
            .iter()
            .find(|tick| tick.agent_id == agent.role)
            .map(|tick| tick.summary.as_str())
            .unwrap_or("No recent tick recorded.");

        let model = model_for_agent(&agent.role, self.product.as_ref());
        let mut content = Column::new()
            .spacing(8)
            .push(
                Row::new()
                    .spacing(12)
                    .align_items(Alignment::Center)
                    .push(
                        text(role_display_name(&agent.role).to_uppercase())
                            .size(12)
                            .style(ACCENT),
                    )
                    .push(Space::with_width(Length::Fill))
                    .push(status_badge(&friendly_status(&agent.status))),
            )
            .push(text(model).size(10).style(TEXT_MUTED))
            .push(text(current_task).size(11).style(TEXT_PRIMARY))
            .push(text(trim_text(action, 96)).size(10).style(TEXT_SECONDARY));

        if self.engineering_mode {
            content = content
                .push(
                    Row::new()
                        .spacing(8)
                        .align_items(Alignment::Center)
                        .push(
                            text(format!("confianca {:.0}%", agent.confidence * 100.0))
                                .size(10)
                                .style(TEXT_MUTED),
                        )
                        .push(
                            container(Space::with_width(Length::Fill).height(2))
                                .style(confidence_bar_style),
                        ),
                )
                .push(
                    Row::new()
                        .spacing(12)
                        .push(
                            text(format!("atencao {}", friendly_risk(&agent.risk_level)))
                                .size(10)
                                .style(risk_color(&agent.risk_level)),
                        )
                        .push(
                            text(format!("estado {}", latency))
                                .size(10)
                                .style(TEXT_MUTED),
                        ),
                )
                .push(
                    text(format!("ultimo sinal {}", heartbeat_age))
                        .size(9)
                        .style(TEXT_MUTED),
                );
        }

        container(content)
            .padding(16)
            .style(agent_card_style)
            .into()
    }

    fn ops_panel(&self) -> Element<'_, Message> {
        let telemetry = self.cognitive_telemetry_panel();

        scrollable(
            Column::new()
                .spacing(16)
                .padding(18)
                .push(text("LINUX PRODUCT").size(13).style(TEXT_PRIMARY))
                .push(
                    container(self.product_status_panel())
                        .padding(12)
                        .style(section_style),
                )
                .push(Rule::horizontal(1).style(rule_style))
                .push(text("OBSERVER ENGINE").size(13).style(TEXT_PRIMARY))
                .push(
                    container(self.observer_content())
                        .padding(12)
                        .style(section_style),
                )
                .push(Rule::horizontal(1).style(rule_style))
                .push(text("INCIDENT CENTER").size(13).style(DANGER))
                .push(
                    container(self.incident_center_content())
                        .padding(12)
                        .style(section_style),
                )
                .push(Rule::horizontal(1).style(rule_style))
                .push(telemetry)
                .push(Rule::horizontal(1).style(rule_style))
                .push(self.activity_panel_compact()),
        )
        .height(Length::Fill)
        .into()
    }

    fn observer_content(&self) -> Column<'_, Message> {
        let mut observer_col = Column::new().spacing(8);
        if let Some(obs) = self.org.observations.first() {
            observer_col = observer_col
                .push(metric_row("Modo", obs.mode.to_uppercase()))
                .push(metric_row("Foco no trabalho", focus_level(obs)))
                .push(metric_row("Git", git_activity(obs)))
                .push(metric_row("Containers", docker_activity(obs)))
                .push(metric_row(
                    "Pressao cognitiva",
                    pressure_label(self.cpu_usage, self.ram_usage),
                ))
                .push(metric_row(
                    "Janela ativa",
                    trim_text(obs.active_window.as_deref().unwrap_or("unknown"), 42),
                ));
        } else {
            observer_col = observer_col.push(
                text("Nenhuma amostra recente do contexto Linux foi persistida.")
                    .size(11)
                    .style(TEXT_MUTED),
            );
        }
        observer_col
    }

    fn incident_center_content(&self) -> Column<'_, Message> {
        let mut incident_col = Column::new().spacing(8);
        for inc in self
            .org
            .incidents
            .iter()
            .take(if self.engineering_mode { 8 } else { 4 })
        {
            let mut body = Column::new()
                .spacing(4)
                .push(
                    Row::new()
                        .push(
                            text(inc.severity.to_uppercase())
                                .size(10)
                                .style(severity_color(&inc.severity)),
                        )
                        .push(Space::with_width(Length::Fill))
                        .push(
                            text(trim_text(&inc.created_at, 19))
                                .size(9)
                                .style(TEXT_MUTED),
                        ),
                )
                .push(
                    text(trim_text(&inc.message, 86))
                        .size(11)
                        .style(TEXT_PRIMARY),
                );
            if self.engineering_mode {
                body = body.push(
                    text(format!(
                        "{} · agent={} · rollback={}",
                        inc.module,
                        inc.agent_id.as_deref().unwrap_or("n/a"),
                        rollback_from_incident(inc)
                    ))
                    .size(10)
                    .style(TEXT_MUTED),
                );
            }
            incident_col = incident_col.push(
                container(body)
                    .padding(8)
                    .width(Length::Fill)
                    .style(incident_row_style),
            );
        }
        if self.org.incidents.is_empty() {
            incident_col = incident_col.push(
                text("Nenhum incidente ativo.")
                    .size(12)
                    .style(TEXT_SECONDARY),
            );
        }
        incident_col
    }

    fn memory_content(&self) -> Column<'_, Message> {
        let mut col = Column::new().spacing(10);
        if let Some(memory) = &self.org.memory {
            col = col
                .push(metric_row("Decisoes", memory.decisions.to_string()))
                .push(metric_row("Eventos", memory.events.to_string()))
                .push(metric_row(
                    "Aprendizados",
                    memory.memory_entries.to_string(),
                ))
                .push(metric_row("Verificacoes", memory.verifications.to_string()));
        }
        for entry in self.org.memory_entries.iter().take(6) {
            col = col.push(
                container(
                    Column::new()
                        .spacing(4)
                        .push(
                            text(format!("{} · {}", entry.kind, entry.scope))
                                .size(10)
                                .style(ACCENT),
                        )
                        .push(
                            text(trim_text(&entry.content, 120))
                                .size(11)
                                .style(TEXT_PRIMARY),
                        )
                        .push(
                            text(trim_text(&entry.created_at, 19))
                                .size(9)
                                .style(TEXT_MUTED),
                        ),
                )
                .padding(10)
                .width(Length::Fill)
                .style(task_row_style),
            );
        }
        if self.org.memory.is_none() && self.org.memory_entries.is_empty() {
            col = col.push(
                text("Memoria organizacional ainda sem dados visiveis.")
                    .size(11)
                    .style(TEXT_MUTED),
            );
        }
        col
    }

    fn product_status_panel(&self) -> Element<'_, Message> {
        if let Some(product) = &self.product {
            let cloud = if product.models.cloud.ready {
                format!(
                    "{} {}",
                    product.models.cloud.provider, product.models.cloud.model
                )
            } else {
                format!(
                    "{} aguardando {}",
                    product.models.cloud.provider, product.models.cloud.api_key_env
                )
            };
            Column::new()
                .spacing(8)
                .push(metric_row(
                    "Pacote",
                    trim_text(&product.paths.project_root, 34),
                ))
                .push(metric_row(
                    "Daemon",
                    friendly_status(&product.daemon.status),
                ))
                .push(metric_row(
                    "Heartbeat",
                    product
                        .daemon
                        .heartbeat_age_s
                        .map(|age| format!("{:.1}s", age))
                        .unwrap_or_else(|| "sem sinal".to_string()),
                ))
                .push(metric_row(
                    "Ollama",
                    product
                        .models
                        .local
                        .selected_model
                        .clone()
                        .unwrap_or_else(|| "sem modelo".to_string()),
                ))
                .push(metric_row("Cloud", trim_text(&cloud, 34)))
                .push(metric_row("Logs", trim_text(&product.paths.log_dir, 34)))
                .into()
        } else {
            container(
                Column::new()
                    .spacing(6)
                    .push(
                        text("Produto ainda nao carregado.")
                            .size(12)
                            .style(TEXT_SECONDARY),
                    )
                    .push(
                        text(
                            self.product_error
                                .as_deref()
                                .unwrap_or("Aguardando retorno de nexus status.")
                                .to_string(),
                        )
                        .size(10)
                        .style(TEXT_MUTED),
                    ),
            )
            .padding(12)
            .width(Length::Fill)
            .style(empty_state_style)
            .into()
        }
    }

    fn cognitive_telemetry_panel(&self) -> Element<'_, Message> {
        let memory = self.org.memory.as_ref();
        let active_ops = self
            .org
            .swarm
            .as_ref()
            .map(|swarm| {
                swarm
                    .tasks
                    .iter()
                    .filter(|task| task.status != "done")
                    .count()
            })
            .unwrap_or(0);
        let agent_pressure = self
            .org
            .swarm
            .as_ref()
            .map(|swarm| {
                swarm
                    .agents
                    .iter()
                    .filter(|agent| agent.status != "idle")
                    .count()
            })
            .unwrap_or(0);
        let runtime_stress = self
            .org
            .commands
            .iter()
            .filter(|cmd| cmd.status == "failed")
            .count();
        let memory_heat = memory
            .map(|m| m.memory_entries + m.events + m.decisions)
            .unwrap_or(0);
        let autonomy =
            std::env::var("NEXUS_AUTONOMY_LEVEL").unwrap_or_else(|_| "GUARDED".to_string());

        let mut content = Column::new()
            .spacing(8)
            .push(text("COGNITIVE TELEMETRY").size(13).style(TEXT_PRIMARY))
            .push(soft_meter(
                "Cognitive Load",
                self.cpu_usage.max(agent_pressure as f32 * 10.0),
                "capacidade mental em uso",
            ))
            .push(soft_meter(
                "Swarm Activity",
                (active_ops as f32 * 12.5).min(100.0),
                "atividade coordenada",
            ))
            .push(soft_meter(
                "Runtime Stress",
                (runtime_stress as f32 * 20.0).min(100.0),
                "pressao de execucao",
            ))
            .push(soft_meter(
                "Memory Heat",
                (memory_heat as f32 / 20.0).min(100.0),
                "memoria operacional",
            ));

        if self.engineering_mode {
            content = content
                .push(metric_row("Agent Pressure", agent_pressure.to_string()))
                .push(metric_row("Runtime Stress", runtime_stress.to_string()))
                .push(metric_row(
                    "Verification Queue",
                    self.org
                        .verifications
                        .iter()
                        .filter(|v| v.status != "passed")
                        .count()
                        .to_string(),
                ))
                .push(metric_row("Autonomy Level", autonomy));
        }

        container(content).padding(12).style(section_style).into()
    }

    fn activity_panel_compact(&self) -> Element<'_, Message> {
        let mut col = Column::new().spacing(8);
        col = col.push(text("ACTIVITY LOG").size(12).style(TEXT_SECONDARY));
        for item in self.visible_activity().iter().rev().take(5) {
            col = col.push(
                text(format!("{} {}", trim_text(&item.timestamp, 8), item.label))
                    .size(10)
                    .style(TEXT_MUTED),
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

    fn find_agent(&self, role: &str) -> Option<&SwarmAgent> {
        self.org
            .swarm
            .as_ref()
            .and_then(|swarm| swarm.agents.iter().find(|agent| agent.role == role))
    }

    fn flow_status_line(&self) -> String {
        let approvals = self.org.approvals.len();
        let incidents = self.org.incidents.len();
        let runtime = self
            .org
            .commands
            .first()
            .map(|command| command.status.as_str())
            .unwrap_or("idle");
        format!(
            "runtime={} · approvals={} · incidents={}",
            runtime, approvals, incidents
        )
    }

    fn active_mission_step(&self) -> &'static str {
        if !self.org.incidents.is_empty() {
            return "security";
        }
        if !self.org.approvals.is_empty() {
            return "security";
        }
        if let Some(command) = self.org.commands.first() {
            let status = command.status.to_ascii_lowercase();
            if status.contains("failed") {
                return "security";
            }
            if status.contains("running") || status.contains("execut") {
                return "runtime";
            }
        }
        if self
            .org
            .verifications
            .iter()
            .any(|item| item.status == "passed")
        {
            return "reviewer";
        }
        if self
            .org
            .swarm
            .as_ref()
            .map(|swarm| swarm.tasks.iter().any(|task| task.owner == "devops"))
            .unwrap_or(false)
        {
            return "devops";
        }
        if self
            .org
            .swarm
            .as_ref()
            .map(|swarm| !swarm.tasks.is_empty())
            .unwrap_or(false)
        {
            return "planner";
        }
        "ceo"
    }

    fn mission_status_line(&self) -> String {
        let active = role_display_name(self.active_mission_step());
        let approvals = self.org.approvals.len();
        let incidents = self.org.incidents.len();
        let result = self
            .org
            .commands
            .first()
            .map(|command| friendly_status(&command.status))
            .unwrap_or_else(|| "aguardando execucao".to_string());
        format!(
            "agora: {} · {} · aprovacoes {} · alertas {}",
            active, result, approvals, incidents
        )
    }

    fn latest_verification_status(&self) -> String {
        self.org
            .verifications
            .first()
            .map(|verification| verification.status.clone())
            .unwrap_or_else(|| "not recorded".to_string())
    }

    fn latest_verification(&self) -> Option<&VerificationItem> {
        self.org.verifications.first()
    }

    fn runtime_log_text(&self) -> String {
        let mut lines = Vec::new();
        if let Some(command) = self.org.commands.first() {
            lines.push(format!("$ {}", command.command));
            lines.push(format!("status: {}", command.status));
            lines.push(format!(
                "exit_code: {}",
                command
                    .exit_code
                    .map(|code| code.to_string())
                    .unwrap_or_else(|| "not captured".to_string())
            ));
        }
        if let Some(verification) = self.latest_verification() {
            lines.push(format!("verification: {}", verification.status));
            if let Some(stdout) = verification
                .evidence
                .get("stdout_tail")
                .and_then(|value| value.as_str())
            {
                lines.push(format!("stdout:\n{}", stdout));
            }
            if let Some(stderr) = verification
                .evidence
                .get("stderr_tail")
                .and_then(|value| value.as_str())
            {
                lines.push(format!("stderr:\n{}", stderr));
            }
        }
        for event in self.org.runtime_events.iter().take(8) {
            lines.push(format!(
                "{} {}",
                event.event_type,
                runtime_event_detail(event)
            ));
        }
        lines.join("\n")
    }

    fn rollback_hint(&self, command: &CommandItem) -> String {
        self.org
            .approvals
            .iter()
            .chain(self.org.approved_commands.iter())
            .find(|approval| {
                command
                    .proposal_id
                    .as_deref()
                    .map(|id| approval_proposal_id(approval) == id)
                    .unwrap_or(false)
            })
            .and_then(|approval| approval.assessment.as_ref())
            .map(|assessment| trim_text(&assessment.rollback, 72))
            .unwrap_or_else(|| "approval rollback metadata unavailable".to_string())
    }

    fn hud_line(&self) -> String {
        let mission = self
            .org
            .swarm
            .as_ref()
            .and_then(|swarm| swarm.current_goal.as_deref())
            .map(|goal| trim_text(goal, 72))
            .unwrap_or_else(|| "no active mission".to_string());
        let runtime = self
            .org
            .commands
            .first()
            .map(|command| format!("cmd {} {}", short_id(&command.command_id), command.status))
            .unwrap_or_else(|| "runtime idle".to_string());
        format!("{} · {} · {}", mission, runtime, self.mission_status_line())
    }

    fn hybrid_routing_line(&self) -> String {
        let Some(product) = &self.product else {
            return "carregando roteador hibrido".to_string();
        };
        let local = product
            .models
            .local
            .selected_model
            .as_deref()
            .unwrap_or("sem modelo local");
        let cloud = if product.models.cloud.ready {
            format!(
                "{} {}",
                product.models.cloud.provider, product.models.cloud.model
            )
        } else {
            format!("{} aguardando chave", product.models.cloud.provider)
        };
        format!(
            "{}: simples/normal no local · complexo/critico na cloud ({})",
            trim_text(local, 22),
            cloud
        )
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
            .spacing(10)
            .push(
                Row::new()
                    .align_items(Alignment::Center)
                    .push(text(label).size(11).style(ACCENT))
                    .push(Space::with_width(Length::Fill))
                    .push(
                        text(friendly_risk(&approval.risk))
                            .size(10)
                            .style(risk_color(&approval.risk)),
                    ),
            )
            .push(
                container(
                    Column::new()
                        .spacing(5)
                        .push(text("Comando").size(10).style(TEXT_MUTED))
                        .push(
                            text(trim_text(&approval.command, 110))
                                .size(11)
                                .style(TEXT_PRIMARY),
                        ),
                )
                .padding(10)
                .width(Length::Fill)
                .style(log_block_style),
            )
            .push(
                Row::new()
                    .spacing(10)
                    .push(decision_info_block(
                        "O que pode acontecer",
                        trim_text(
                            assessment
                                .map(|item| item.impact.as_str())
                                .unwrap_or("impacto nao informado"),
                            90,
                        ),
                        TEXT_SECONDARY,
                    ))
                    .push(decision_info_block(
                        "Como desfazer",
                        trim_text(
                            assessment
                                .map(|item| item.rollback.as_str())
                                .unwrap_or("rollback nao informado"),
                            90,
                        ),
                        WARNING,
                    )),
            )
            .push(decision_info_block(
                "Avisos",
                trim_text(&warnings, 110),
                if warnings == "sem avisos adicionais" {
                    TEXT_MUTED
                } else {
                    WARNING
                },
            ));

        let mut action_button = button(text(action_label).size(11));
        if !self.org_action_in_flight {
            if let Some(message) = action {
                action_button = action_button.on_press(message);
            }
        }
        content = content.push(action_button);

        container(content)
            .padding(12)
            .width(Length::Fill)
            .style(feedback_card_style)
            .into()
    }
}

fn section_block<'a>(title: &'static str, body: Column<'a, Message>) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(12)
            .push(
                Row::new()
                    .spacing(10)
                    .align_items(Alignment::Center)
                    .push(text(route_icon_for_title(title)).size(16).style(CYAN))
                    .push(text(title).size(13).style(TEXT_PRIMARY)),
            )
            .push(body),
    )
    .padding(18)
    .width(Length::Fill)
    .style(nexus_card_style)
    .into()
}

fn page_header<'a>(title: &'static str, subtitle: &'static str) -> Element<'a, Message> {
    container(
        Row::new()
            .spacing(16)
            .align_items(Alignment::Center)
            .push(
                container(text(route_icon_for_title(title)).size(28).style(CYAN))
                    .padding(12)
                    .style(nexus_metric_icon_style),
            )
            .push(
                Column::new()
                    .spacing(6)
                    .push(text(title).size(30).style(TEXT_PRIMARY))
                    .push(text(subtitle).size(14).style(TEXT_SECONDARY)),
            ),
    )
    .padding([8, 0])
    .width(Length::Fill)
    .into()
}

fn prompt_mode_row<'a>() -> Element<'a, Message> {
    Row::new()
        .spacing(8)
        .push(prompt_chip("Análise", "entender e explicar", ACCENT))
        .push(prompt_chip("Modificação", "mudar com evidência", PURPLE))
        .push(prompt_chip("Execução", "rodar e verificar", WARNING))
        .into()
}

fn prompt_chip<'a>(
    label: &'static str,
    detail: &'static str,
    color: Color,
) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(3)
            .push(text(label).size(11).style(color))
            .push(text(detail).size(9).style(TEXT_MUTED)),
    )
    .padding([8, 10])
    .width(Length::FillPortion(1))
    .style(overview_chip_style)
    .into()
}

fn hud_metric_tile<'a>(label: &'static str, value: String, color: Color) -> Element<'a, Message> {
    container(
        Row::new()
            .spacing(10)
            .align_items(Alignment::Center)
            .push(text("●").size(10).style(color))
            .push(
                Column::new()
                    .spacing(3)
                    .push(text(label).size(10).style(TEXT_MUTED))
                    .push(text(value).size(12).style(TEXT_PRIMARY)),
            ),
    )
    .padding(10)
    .width(Length::Fill)
    .style(hud_tile_style)
    .into()
}

fn hud_meter_tile<'a>(label: &'static str, value: f32, color: Color) -> Element<'a, Message> {
    let fill = value.clamp(4.0, 100.0) * 1.5;
    container(
        Column::new()
            .spacing(7)
            .push(
                Row::new()
                    .push(text(label).size(10).style(TEXT_MUTED))
                    .push(Space::with_width(Length::Fill))
                    .push(text(format!("{:.0}%", value)).size(10).style(color)),
            )
            .push(
                Row::new()
                    .spacing(6)
                    .align_items(Alignment::Center)
                    .push(container(Space::new(fill, 5)).style(match label {
                        "MEMORY" => meter_fill_warning_style,
                        _ => meter_fill_accent_style,
                    }))
                    .push(
                        container(Space::with_width(Length::Fill).height(5))
                            .style(meter_track_style),
                    ),
            ),
    )
    .padding(10)
    .width(Length::Fill)
    .style(hud_tile_style)
    .into()
}

fn hud_orbit_chip<'a>(label: &'static str, value: String, color: Color) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(3)
            .align_items(Alignment::Center)
            .push(text(label).size(9).style(TEXT_MUTED))
            .push(text(value).size(12).style(color)),
    )
    .padding([7, 10])
    .style(hud_orbit_chip_style)
    .into()
}

fn nexus_summary_metric<'a>(
    icon: &'static str,
    label: &'static str,
    value: String,
    detail: &'static str,
    color: Color,
) -> Element<'a, Message> {
    Row::new()
        .spacing(14)
        .align_items(Alignment::Center)
        .push(
            container(text(icon).size(27).style(color))
                .padding(15)
                .style(nexus_metric_icon_style),
        )
        .push(
            Column::new()
                .spacing(5)
                .push(text(label).size(14).style(TEXT_SECONDARY))
                .push(text(value).size(20).style(color))
                .push(text(detail).size(12).style(TEXT_MUTED)),
        )
        .width(Length::FillPortion(1))
        .into()
}

fn performance_label(cpu: f32) -> String {
    if cpu < 60.0 {
        "Ótimo".to_string()
    } else if cpu < 82.0 {
        "Alto".to_string()
    } else {
        "Crítico".to_string()
    }
}

fn activity_symbol(level: &ActivityLevel) -> &'static str {
    match level {
        ActivityLevel::Info => "i",
        ActivityLevel::Success => "✓",
        ActivityLevel::Warning => "!",
        ActivityLevel::Error => "×",
    }
}

fn route_icon_for_title(title: &str) -> &'static str {
    match title {
        "Painel do NEXUS" | "Conversar" | "Fale com o NEXUS" => "◌",
        "Visão Geral" => "▦",
        "Missoes" | "Missões" | "Tarefas" | "PENDENTES" => "☑",
        "Swarm" | "EQUIPE COGNITIVA" => "⇄",
        "Execucoes" | "Execuções" | "EXECUCAO" | "PRONTAS PARA EXECUTAR" => "⌁",
        "Aprovacoes" | "Aprovações" | "APROVACAO SELECIONADA" => "✓",
        "Incidentes" => "!",
        "Observador" => "◎",
        "Telemetria" => "◍",
        "Memoria" | "Memória" => "◇",
        "Config" | "Configurações" => "⚙",
        _ => "▱",
    }
}

fn guidance_card<'a>(
    title: &'static str,
    detail: &'static str,
    color: Color,
) -> Element<'a, Message> {
    container(
        Row::new()
            .spacing(10)
            .align_items(Alignment::Center)
            .push(text("●").size(10).style(color))
            .push(
                Column::new()
                    .spacing(3)
                    .push(text(title).size(11).style(TEXT_PRIMARY))
                    .push(text(detail).size(10).style(TEXT_MUTED)),
            ),
    )
    .padding(10)
    .width(Length::Fill)
    .style(overview_chip_style)
    .into()
}

fn feedback_card<'a>(feedback: &'a ChatFeedback) -> Element<'a, Message> {
    let mut evidence = Column::new().spacing(4);
    for item in feedback.evidence.iter().take(3) {
        evidence = evidence.push(
            text(format!("• {}", trim_text(item, 96)))
                .size(10)
                .style(TEXT_MUTED),
        );
    }
    if feedback.evidence.is_empty() {
        evidence = evidence.push(
            text("• Sem evidência operacional anexada.")
                .size(10)
                .style(TEXT_MUTED),
        );
    }

    let mut next_steps = Column::new().spacing(4);
    for item in feedback.next_steps.iter().take(2) {
        next_steps = next_steps.push(
            text(format!("• {}", trim_text(item, 86)))
                .size(10)
                .style(TEXT_SECONDARY),
        );
    }

    container(
        Column::new()
            .spacing(8)
            .push(
                Row::new()
                    .spacing(8)
                    .align_items(Alignment::Center)
                    .push(text(&feedback.intent_label).size(10).style(ACCENT))
                    .push(text("·").size(10).style(TEXT_MUTED))
                    .push(text(&feedback.status_label).size(10).style(SUCCESS))
                    .push(Space::with_width(Length::Fill))
                    .push(
                        text(format!("Confiança {}", feedback.confidence_label))
                            .size(10)
                            .style(TEXT_MUTED),
                    ),
            )
            .push(text(&feedback.user_hint).size(10).style(TEXT_SECONDARY))
            .push(
                Row::new()
                    .spacing(12)
                    .push(
                        Column::new()
                            .spacing(5)
                            .width(Length::FillPortion(1))
                            .push(text("Evidências").size(10).style(TEXT_PRIMARY))
                            .push(evidence),
                    )
                    .push(
                        Column::new()
                            .spacing(5)
                            .width(Length::FillPortion(1))
                            .push(text("Próximos passos").size(10).style(TEXT_PRIMARY))
                            .push(next_steps),
                    ),
            ),
    )
    .padding(10)
    .width(Length::Fill)
    .style(feedback_card_style)
    .into()
}

fn decision_info_block<'a>(
    label: &'static str,
    value: String,
    color: Color,
) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(5)
            .push(text(label).size(10).style(TEXT_MUTED))
            .push(text(value).size(10).style(color)),
    )
    .padding(10)
    .width(Length::FillPortion(1))
    .style(task_row_style)
    .into()
}

fn header_status_card<'a>(
    label: &'static str,
    value: String,
    detail: String,
    color: Color,
) -> Element<'a, Message> {
    container(
        Row::new()
            .spacing(10)
            .align_items(Alignment::Center)
            .push(text("●").size(13).style(color))
            .push(
                Column::new()
                    .spacing(2)
                    .push(text(label).size(11).style(TEXT_PRIMARY))
                    .push(text(value).size(10).style(TEXT_SECONDARY))
                    .push(text(detail).size(9).style(color)),
            ),
    )
    .padding([8, 12])
    .width(Length::Fixed(156.0))
    .style(header_chip_style)
    .into()
}

fn mission_fact<'a>(label: &'static str, value: String, color: Color) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(4)
            .push(text(label).size(10).style(TEXT_MUTED))
            .push(text(value).size(11).style(color)),
    )
    .width(Length::FillPortion(1))
    .into()
}

fn ai_route_card<'a>(
    title: &'static str,
    model: String,
    detail: &'static str,
    color: Color,
) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(7)
            .push(
                Row::new()
                    .spacing(8)
                    .align_items(Alignment::Center)
                    .push(text("✣").size(14).style(color))
                    .push(text(title).size(11).style(TEXT_PRIMARY)),
            )
            .push(text(model).size(11).style(TEXT_SECONDARY))
            .push(text(detail).size(10).style(TEXT_MUTED)),
    )
    .padding(12)
    .width(Length::FillPortion(1))
    .style(ai_card_style)
    .into()
}

fn system_status_row<'a>(label: &'static str, value: String, color: Color) -> Element<'a, Message> {
    Row::new()
        .spacing(10)
        .align_items(Alignment::Center)
        .push(text(label).size(11).style(TEXT_SECONDARY))
        .push(Space::with_width(Length::Fill))
        .push(text(value).size(11).style(color))
        .into()
}

fn system_meter_row<'a>(label: &'static str, value: f32) -> Element<'a, Message> {
    let clamped = value.clamp(0.0, 100.0);
    let fill = (clamped * 1.05).max(8.0);
    let fill_style: fn(&Theme) -> container::Appearance = if clamped > 78.0 {
        meter_fill_warning_style
    } else if clamped > 48.0 {
        meter_fill_accent_style
    } else {
        meter_fill_success_style
    };

    Row::new()
        .spacing(10)
        .align_items(Alignment::Center)
        .push(
            text(label)
                .size(11)
                .style(TEXT_SECONDARY)
                .width(Length::Fixed(112.0)),
        )
        .push(
            Row::new()
                .spacing(0)
                .push(container(Space::new(fill, 5)).style(fill_style))
                .push(container(Space::with_width(Length::Fill).height(5)).style(meter_track_style))
                .width(Length::Fill),
        )
        .push(
            text(format!("{:.0}%", clamped))
                .size(11)
                .style(TEXT_PRIMARY),
        )
        .into()
}

fn team_member_row<'a>(
    role: &'static str,
    task: &'static str,
    status: String,
    model: String,
) -> Element<'a, Message> {
    container(
        Row::new()
            .spacing(10)
            .align_items(Alignment::Center)
            .push(
                container(text("⌘").size(12).style(TEXT_PRIMARY))
                    .padding(8)
                    .style(agent_avatar_style),
            )
            .push(
                Column::new()
                    .spacing(2)
                    .width(Length::Fill)
                    .push(text(role).size(12).style(TEXT_PRIMARY))
                    .push(text(task).size(10).style(TEXT_MUTED)),
            )
            .push(text(status).size(10).style(SUCCESS))
            .push(text(trim_text(&model, 14)).size(10).style(TEXT_SECONDARY)),
    )
    .padding([7, 8])
    .width(Length::Fill)
    .style(task_row_style)
    .into()
}

fn timeline_point<'a>(
    time: &str,
    label: &'static str,
    detail: &'static str,
    color: Color,
) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(6)
            .width(Length::FillPortion(1))
            .push(text(time.to_string()).size(10).style(TEXT_MUTED))
            .push(text("●").size(13).style(color))
            .push(text(label).size(11).style(TEXT_PRIMARY))
            .push(text(detail).size(10).style(TEXT_SECONDARY)),
    )
    .width(Length::FillPortion(1))
    .into()
}

fn activity_color(level: &ActivityLevel) -> Color {
    match level {
        ActivityLevel::Info => ACCENT,
        ActivityLevel::Success => SUCCESS,
        ActivityLevel::Warning => WARNING,
        ActivityLevel::Error => DANGER,
    }
}

fn role_summary_card<'a>(
    label: &'static str,
    body: &'static str,
    color: Color,
) -> Element<'a, Message> {
    container(
        Row::new()
            .spacing(12)
            .align_items(Alignment::Center)
            .push(
                container(text(role_icon(label)).size(16).style(color))
                    .padding(10)
                    .style(nexus_update_icon_style),
            )
            .push(
                Column::new()
                    .spacing(5)
                    .push(text(label).size(12).style(color))
                    .push(text(body).size(11).style(TEXT_SECONDARY)),
            ),
    )
    .padding(14)
    .width(Length::FillPortion(1))
    .style(nexus_card_style)
    .into()
}

fn role_icon(label: &str) -> &'static str {
    match label {
        "CEO" => "◇",
        "CTO" => "⌁",
        "Usuario" | "Usuário" => "◌",
        _ => "▱",
    }
}

fn simple_card<'a>(
    title: &'static str,
    value: String,
    detail: &'static str,
    color: Color,
) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(8)
            .push(text(title).size(11).style(TEXT_MUTED))
            .push(text(value).size(15).style(color))
            .push(text(detail).size(10).style(TEXT_SECONDARY)),
    )
    .padding(14)
    .width(Length::FillPortion(1))
    .style(simple_card_style)
    .into()
}

fn empty_state<'a>(title: &'static str, detail: &'static str) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(6)
            .push(text(title).size(12).style(TEXT_SECONDARY))
            .push(text(detail).size(10).style(TEXT_MUTED)),
    )
    .padding(12)
    .width(Length::Fill)
    .style(empty_state_style)
    .into()
}

fn log_block<'a>(label: &'static str, content: &str, color: Color) -> Element<'a, Message> {
    let value = if content.trim().is_empty() {
        "no output captured".to_string()
    } else {
        trim_text(content, 520)
    };
    container(
        Column::new()
            .spacing(5)
            .push(text(label.to_uppercase()).size(10).style(color))
            .push(text(value).size(11).style(TEXT_PRIMARY)),
    )
    .padding(10)
    .width(Length::Fill)
    .style(log_block_style)
    .into()
}

fn summary_banner<'a>(title: String, detail: String, color: Color) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(6)
            .push(text(title).size(13).style(TEXT_PRIMARY))
            .push(text(detail).size(11).style(color)),
    )
    .padding(12)
    .width(Length::Fill)
    .style(summary_banner_style)
    .into()
}

fn technical_detail_block<'a>(command: &CommandItem) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(4)
            .push(text("detalhes tecnicos").size(10).style(TEXT_MUTED))
            .push(
                text(format!("comando: {}", trim_text(&command.command, 96)))
                    .size(10)
                    .style(TEXT_MUTED),
            )
            .push(
                text(format!("cwd: {}", trim_text(&command.cwd, 96)))
                    .size(10)
                    .style(TEXT_MUTED),
            )
            .push(
                text(format!("id: {}", short_id(&command.command_id)))
                    .size(10)
                    .style(TEXT_MUTED),
            ),
    )
    .padding(10)
    .width(Length::Fill)
    .style(technical_block_style)
    .into()
}

fn status_badge<'a>(status: &str) -> Element<'a, Message> {
    container(
        text(status.to_uppercase())
            .size(9)
            .style(status_color(status)),
    )
    .padding([3, 8])
    .style(status_pill_style)
    .into()
}

fn runtime_line<'a>(label: &str, value: &str, color: Color) -> Row<'a, Message> {
    Row::new()
        .spacing(10)
        .align_items(Alignment::Center)
        .push(
            text(label.to_string())
                .size(10)
                .width(Length::Fixed(92.0))
                .style(ACCENT),
        )
        .push(
            text(value.to_string())
                .size(11)
                .width(Length::Fill)
                .style(color),
        )
}

fn metric_row<'a>(label: &'static str, value: String) -> Row<'a, Message> {
    Row::new()
        .align_items(Alignment::Center)
        .push(text(label).size(12).style(TEXT_SECONDARY))
        .push(Space::with_width(Length::Fill))
        .push(text(value).size(12).style(TEXT_PRIMARY))
}

fn soft_meter<'a>(label: &'static str, value: f32, hint: &'static str) -> Element<'a, Message> {
    let clamped = value.clamp(0.0, 100.0);
    let fill = (clamped * 1.8).max(8.0);
    let color = if clamped > 78.0 {
        WARNING
    } else if clamped > 48.0 {
        ACCENT
    } else {
        SUCCESS
    };
    let fill_style: fn(&Theme) -> container::Appearance = if clamped > 78.0 {
        meter_fill_warning_style
    } else if clamped > 48.0 {
        meter_fill_accent_style
    } else {
        meter_fill_success_style
    };
    container(
        Column::new()
            .spacing(6)
            .push(
                Row::new()
                    .push(text(label).size(11).style(TEXT_SECONDARY))
                    .push(Space::with_width(Length::Fill))
                    .push(text(format!("{:.0}%", clamped)).size(11).style(color)),
            )
            .push(
                Row::new()
                    .push(container(Space::new(fill, 5)).style(fill_style))
                    .push(
                        container(Space::with_width(Length::Fill).height(5))
                            .style(meter_track_style),
                    ),
            )
            .push(text(hint).size(9).style(TEXT_MUTED)),
    )
    .padding([8, 0])
    .width(Length::Fill)
    .into()
}

fn status_color(status: &str) -> Color {
    match status.to_ascii_lowercase().as_str() {
        "completed" | "executed" | "passed" | "done" | "success" => SUCCESS,
        "running" | "assigned" | "planning" | "verifying" | "ready" => ACCENT,
        "approval_pending" | "pending_approval" | "blocked" | "rollback" => WARNING,
        "failed" | "error" | "offline" => DANGER,
        _ => TEXT_MUTED,
    }
}

fn risk_color(risk: &str) -> Color {
    match risk.to_ascii_lowercase().as_str() {
        "high" | "critical" => DANGER,
        "medium" => WARNING,
        "low" => SUCCESS,
        _ => TEXT_MUTED,
    }
}

fn severity_color(severity: &str) -> Color {
    match severity.to_ascii_lowercase().as_str() {
        "critical" | "error" | "high" => DANGER,
        "warning" | "medium" => WARNING,
        _ => ACCENT,
    }
}

fn role_display_name(role: &str) -> &'static str {
    match role {
        "ceo" => "Prioriza",
        "planner" => "Planeja",
        "devops" => "Executa",
        "reviewer" => "Revisa",
        "security" => "Protege",
        "runtime" => "Runtime",
        "memory" => "Memoria",
        "observer" => "Observa",
        "coder" => "Constrói",
        "cto" => "Arquitetura",
        _ => "Agente",
    }
}

fn role_action_label(role: &str) -> &'static str {
    match role {
        "ceo" => "decide prioridade",
        "planner" => "organiza etapas",
        "devops" => "prepara ambiente",
        "reviewer" => "confere resultado",
        "security" => "controla risco",
        "runtime" => "roda a acao",
        "memory" => "registra aprendizado",
        "observer" => "le o Linux",
        "coder" => "altera codigo",
        "cto" => "define arquitetura",
        _ => "acompanha",
    }
}

fn model_for_agent(role: &str, product: Option<&ProductStatus>) -> String {
    let local = product
        .and_then(|item| item.models.local.selected_model.as_deref())
        .unwrap_or("Local AI");
    let cloud = product
        .map(|item| {
            if item.models.cloud.ready {
                item.models.cloud.model.as_str()
            } else {
                "Cloud AI"
            }
        })
        .unwrap_or("Cloud AI");
    match role {
        "ceo" | "planner" | "reviewer" | "cto" => format!("{} CLOUD", cloud),
        "observer" | "memory" | "runtime" | "devops" => format!("{} LOCAL", local),
        "security" | "guardian" => "HYBRID".to_string(),
        _ => "HYBRID".to_string(),
    }
}

fn next_action_for_role(role: &str, app: &NexusApp) -> &'static str {
    match role {
        "security" if !app.org.approvals.is_empty() => "precisa aprovar",
        "security" if !app.org.incidents.is_empty() => "alerta aberto",
        "runtime" if app.org.commands.is_empty() => "sem execucao",
        "runtime" => "com evidencia",
        "reviewer" if !app.org.verifications.is_empty() => "verificado",
        "devops" if app.org.commands.is_empty() => "aguardando runtime",
        "planner" => "plano ativo",
        "ceo" => "missao ativa",
        _ => "em espera",
    }
}

fn friendly_status(status: &str) -> String {
    match status.to_ascii_lowercase().as_str() {
        "active" => "em foco".to_string(),
        "assigned" => "trabalhando".to_string(),
        "idle" => "aguardando".to_string(),
        "running" => "executando".to_string(),
        "executed" | "completed" | "done" | "passed" | "success" => "concluido".to_string(),
        "pending_approval" | "approval_pending" => "aguardando aprovacao".to_string(),
        "blocked" => "bloqueado".to_string(),
        "failed" | "error" => "falhou".to_string(),
        "ready" => "pronto".to_string(),
        other => other.replace('_', " "),
    }
}

fn friendly_lifecycle(status: &str) -> String {
    match status {
        "CREATED" => "criada".to_string(),
        "PLANNING" => "planejando".to_string(),
        "APPROVAL_PENDING" => "aguardando aprovacao".to_string(),
        "RUNNING" => "executando".to_string(),
        "VERIFYING" => "verificando".to_string(),
        "COMPLETED" => "concluida".to_string(),
        "FAILED" => "falhou".to_string(),
        "ROLLBACK" => "revertendo".to_string(),
        other => other.to_ascii_lowercase(),
    }
}

fn friendly_risk(risk: &str) -> &'static str {
    match risk.to_ascii_lowercase().as_str() {
        "high" | "critical" => "alta",
        "medium" => "media",
        "low" => "baixa",
        _ => "normal",
    }
}

fn human_command_label(command: &str) -> String {
    let lower = command.to_ascii_lowercase();
    if lower.contains("python") && lower.contains("--version") {
        "Conferindo a versao do Python".to_string()
    } else if lower.contains("cargo build") {
        "Compilando o modulo Rust".to_string()
    } else if lower.contains("pytest") {
        "Rodando testes automatizados".to_string()
    } else if lower.contains("systemctl") {
        "Verificando ou alterando servico do sistema".to_string()
    } else if lower.contains("docker") || lower.contains("podman") {
        "Inspecionando runtime de containers".to_string()
    } else {
        trim_text(command, 72)
    }
}

fn human_task_title(task: &SwarmTask) -> String {
    let title = task.title.as_str();
    if title.contains("Define objective") {
        "Definir objetivo e criterio de sucesso".to_string()
    } else if title.contains("Break objective") || title.starts_with("Plan:") {
        "Organizar a missao em etapas".to_string()
    } else if title.contains("Evaluate risks") || title.contains("Guardian") {
        "Checar risco e aprovacoes".to_string()
    } else if title.contains("Persist decisions") {
        "Registrar decisoes e evidencias".to_string()
    } else if title.contains("Observe Linux") {
        "Observar contexto do Linux".to_string()
    } else if title.contains("Validate runtime") {
        "Validar ambiente e execucao".to_string()
    } else if title.contains("Review") {
        "Revisar resultado".to_string()
    } else if title.contains("CEO intake") {
        "Receber e priorizar a missao".to_string()
    } else {
        title.to_string()
    }
}

fn execution_summary(command: &CommandItem, verification: Option<&VerificationItem>) -> String {
    let action = human_command_label(&command.command);
    let status = friendly_status(&command.status);
    let verified = verification
        .map(|item| friendly_status(&item.status))
        .unwrap_or_else(|| "sem verificacao registrada".to_string());
    format!("{} · {} · {}", action, status, verified)
}

fn execution_result_label(
    command: &CommandItem,
    verification: Option<&VerificationItem>,
) -> String {
    if command.status == "failed" {
        "Ação falhou; revisar evidência antes de continuar.".to_string()
    } else if verification.map(|item| item.status.as_str()) == Some("passed") {
        "Resultado verificado com evidência real.".to_string()
    } else if command.status == "executed" {
        "Ação executada; verificação pendente ou não exibida.".to_string()
    } else {
        "Aguardando runtime ou saída persistida.".to_string()
    }
}

fn lifecycle_state(task: &SwarmTask) -> String {
    let raw = task.status.to_ascii_lowercase();
    if raw.contains("fail") {
        "FAILED".to_string()
    } else if raw.contains("verify") {
        "VERIFYING".to_string()
    } else if raw.contains("run") || raw.contains("execut") {
        "RUNNING".to_string()
    } else if raw.contains("approval") {
        "APPROVAL_PENDING".to_string()
    } else if raw.contains("done") || raw.contains("complete") {
        "COMPLETED".to_string()
    } else if raw.contains("plan") {
        "PLANNING".to_string()
    } else {
        "CREATED".to_string()
    }
}

fn timestamp_for_task(task: &SwarmTask) -> String {
    trim_text(task.updated_at.as_deref().unwrap_or(&task.created_at), 19)
}

fn task_priority(task: &SwarmTask) -> String {
    task.metadata
        .get("priority")
        .and_then(|value| value.as_i64())
        .map(|value| value.to_string())
        .unwrap_or_else(|| "n/a".to_string())
}

fn task_risk(task: &SwarmTask) -> String {
    task.metadata
        .get("risk_level")
        .and_then(|value| value.as_str())
        .unwrap_or("low")
        .to_string()
}

fn task_last_action(task: &SwarmTask) -> String {
    task.metadata
        .get("success_criteria")
        .and_then(|value| value.as_array())
        .and_then(|items| items.first())
        .and_then(|value| value.as_str())
        .map(|value| trim_text(value, 54))
        .unwrap_or_else(|| "queued in shared blackboard".to_string())
}

fn task_progress(lifecycle: &str) -> &'static str {
    match lifecycle {
        "CREATED" => "10%",
        "PLANNING" => "25%",
        "APPROVAL_PENDING" => "35%",
        "RUNNING" => "60%",
        "VERIFYING" => "80%",
        "COMPLETED" => "100%",
        "FAILED" => "halted",
        "ROLLBACK" => "rollback",
        _ => "queued",
    }
}

fn friendly_task_status(status: &str) -> &'static str {
    match status.to_ascii_lowercase().as_str() {
        "done" | "completed" | "complete" => "Concluída",
        "running" | "active" | "in_progress" | "progress" => "Em andamento",
        "blocked" | "failed" => "Precisa atenção",
        "queued" | "pending" | "created" => "Pendente",
        _ => "Planejada",
    }
}

fn runtime_event_detail(event: &RuntimeEvent) -> String {
    if !event.message.is_empty() {
        return event.message.clone();
    }
    if !event.payload.is_null() {
        return compact_json(&event.payload, 120);
    }
    format!(
        "{} {}",
        event.command_id.as_deref().unwrap_or("no-command"),
        event.stream.as_deref().unwrap_or("")
    )
}

fn focus_level(obs: &ObservationItem) -> String {
    let text = format!(
        "{} {}",
        obs.active_window.as_deref().unwrap_or(""),
        compact_json(&serde_json::Value::Array(obs.triggers.clone()), 160)
    )
    .to_ascii_lowercase();
    if text.contains("code") || text.contains("vscode") || text.contains("terminal") {
        "HIGH".to_string()
    } else if obs.confidence > 0.55 {
        "MEDIUM".to_string()
    } else {
        "LOW".to_string()
    }
}

fn git_activity(obs: &ObservationItem) -> String {
    let text =
        compact_json(&serde_json::Value::Array(obs.triggers.clone()), 240).to_ascii_lowercase();
    if text.contains("git") {
        "ACTIVE".to_string()
    } else {
        "QUIET".to_string()
    }
}

fn docker_activity(obs: &ObservationItem) -> String {
    let text =
        compact_json(&serde_json::Value::Array(obs.processes.clone()), 480).to_ascii_lowercase();
    if text.contains("docker") || text.contains("podman") {
        "RUNNING".to_string()
    } else {
        "NOT VISIBLE".to_string()
    }
}

fn pressure_label(cpu: f32, ram: f32) -> String {
    if cpu > 80.0 || ram > 88.0 {
        "HIGH".to_string()
    } else if cpu > 55.0 || ram > 70.0 {
        "MEDIUM".to_string()
    } else {
        "LOW".to_string()
    }
}

fn rollback_from_incident(incident: &IncidentItem) -> String {
    incident
        .metadata
        .get("rollback")
        .and_then(|value| value.as_str())
        .map(|value| trim_text(value, 36))
        .unwrap_or_else(|| "review command evidence".to_string())
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

fn overview_chip<'a>(label: &'static str, value: String, color: Color) -> Element<'a, Message> {
    container(
        Column::new()
            .spacing(4)
            .push(text(label).size(10).style(TEXT_MUTED))
            .push(text(value).size(12).style(color)),
    )
    .padding([10, 12])
    .width(Length::FillPortion(1))
    .style(overview_chip_style)
    .into()
}

fn icon<'a>(icon: NexusIcon, size: u16, color: Color) -> Element<'a, Message> {
    Svg::new(svg::Handle::from_memory(icon.svg().as_bytes()))
        .width(Length::Fixed(size as f32))
        .height(Length::Fixed(size as f32))
        .style(theme::Svg::Custom(Box::new(IconSvgStyle { color })))
        .into()
}

fn tooltip_label<'a>(
    content: Element<'a, Message>,
    label: &'static str,
    position: tooltip::Position,
) -> Element<'a, Message> {
    Tooltip::new(content, text(label).size(11).style(TEXT_PRIMARY), position)
        .gap(8)
        .padding(8)
        .style(tooltip_style)
        .into()
}

fn icon_button<'a>(
    icon_kind: NexusIcon,
    label: &'static str,
    message: Option<Message>,
    style: IconButtonStyle,
) -> Element<'a, Message> {
    let mut control = button(icon(icon_kind, style.icon_size, style.icon_color()))
        .padding(style.padding)
        .width(Length::Fixed(style.size))
        .height(Length::Fixed(style.size))
        .style(theme::Button::custom(style));

    if let Some(message) = message {
        control = control.on_press(message);
    }

    tooltip_label(control.into(), label, tooltip::Position::Top)
}

fn sidebar_item<'a>(
    icon_kind: NexusIcon,
    label: &'static str,
    active: bool,
    message: Message,
) -> Element<'a, Message> {
    let item = button(
        Row::new()
            .spacing(12)
            .align_items(Alignment::Center)
            .push(
                container(icon(icon_kind, 18, if active { CYAN } else { TEXT_MUTED }))
                    .padding(9)
                    .style(if active {
                        nexus_metric_icon_style
                    } else {
                        nexus_update_icon_style
                    }),
            )
            .push(
                text(label)
                    .size(14)
                    .style(if active { TEXT_PRIMARY } else { TEXT_SECONDARY }),
            ),
    )
    .padding([8, 10])
    .width(Length::Fill)
    .style(theme::Button::custom(SidebarButtonStyle { active }))
    .on_press(message);

    container(item)
        .width(Length::Fill)
        .style(if active {
            sidebar_item_active_style
        } else {
            sidebar_item_style
        })
        .into()
}

fn prompt_card<'a>(
    icon_kind: NexusIcon,
    title: &'static str,
    detail: &'static str,
    prompt: &'static str,
    width: Length,
) -> Element<'a, Message> {
    button(
        Column::new()
            .spacing(14)
            .push(
                container(icon(icon_kind, 22, CYAN))
                    .padding(9)
                    .style(prompt_icon_style),
            )
            .push(
                Column::new()
                    .spacing(7)
                    .push(text(title).size(14).style(TEXT_PRIMARY))
                    .push(text(detail).size(13).style(TEXT_SECONDARY)),
            ),
    )
    .padding(18)
    .width(width)
    .height(Length::Fixed(132.0))
    .style(theme::Button::custom(SuggestionButtonStyle))
    .on_press(Message::PromptSelected(prompt))
    .into()
}

fn premium_task_item<'a>(
    title: impl Into<String>,
    status: impl Into<String>,
    detail: impl Into<String>,
) -> Element<'a, Message> {
    container(
        Row::new()
            .spacing(14)
            .align_items(Alignment::Center)
            .push(
                container(icon(NexusIcon::Check, 16, CYAN))
                    .padding(10)
                    .style(prompt_icon_style),
            )
            .push(
                Column::new()
                    .spacing(5)
                    .push(text(title.into()).size(15).style(TEXT_PRIMARY))
                    .push(text(detail.into()).size(13).style(TEXT_SECONDARY)),
            )
            .push(Space::with_width(Length::Fill))
            .push(
                container(text(status.into()).size(12).style(CYAN))
                    .padding([8, 12])
                    .style(chat_status_pill_style),
            ),
    )
    .padding(16)
    .width(Length::Fill)
    .style(premium_surface_style)
    .into()
}

fn settings_item<'a>(
    title: &'static str,
    detail: &'static str,
    value: &'static str,
    color: Color,
) -> Element<'a, Message> {
    container(
        Row::new()
            .spacing(14)
            .align_items(Alignment::Center)
            .push(container(Space::new(10, 10)).style(settings_dot_style))
            .push(
                Column::new()
                    .spacing(5)
                    .push(text(title).size(15).style(TEXT_PRIMARY))
                    .push(text(detail).size(13).style(TEXT_SECONDARY)),
            )
            .push(Space::with_width(Length::Fill))
            .push(text(value).size(13).style(color)),
    )
    .padding(18)
    .width(Length::Fill)
    .style(premium_surface_style)
    .into()
}

fn chat_message_row<'a>(msg: &'a ChatMessage, compact: bool) -> Element<'a, Message> {
    let is_operator = msg.role == "OPERATOR";
    let is_error = msg.role == "CORE_ERROR";
    let bubble_width = if compact {
        Length::Fill
    } else if is_operator {
        Length::Fixed(430.0)
    } else {
        Length::Fixed(480.0)
    };

    let content = trim_text(&msg.content, if compact { 420 } else { 620 });
    let bubble_style: fn(&Theme) -> container::Appearance = if is_error {
        error_bubble_modern
    } else if is_operator {
        operator_bubble_modern
    } else {
        nexus_bubble_modern
    };

    let bubble = container(
        text(content)
            .size(15)
            .style(TEXT_PRIMARY)
            .width(Length::Fill),
    )
    .padding([14, 18])
    .width(bubble_width)
    .style(bubble_style);

    if is_operator {
        let stack = Column::new()
            .spacing(6)
            .align_items(Alignment::End)
            .push(bubble)
            .push(text(format!("{} ✓✓", msg.timestamp)).size(12).style(CYAN));

        if compact {
            Row::new()
                .width(Length::Fill)
                .push(Space::with_width(Length::Fixed(36.0)))
                .push(stack.width(Length::Fill))
                .into()
        } else {
            Row::new()
                .width(Length::Fill)
                .push(Space::with_width(Length::Fill))
                .push(stack)
                .into()
        }
    } else {
        let avatar = container(text("N").size(18).style(CYAN))
            .padding(8)
            .style(chat_message_avatar_style);
        let stack = Column::new()
            .spacing(6)
            .push(bubble)
            .push(text(&msg.timestamp).size(12).style(TEXT_MUTED));

        if compact {
            Row::new()
                .spacing(10)
                .align_items(Alignment::Start)
                .width(Length::Fill)
                .push(avatar)
                .push(stack.width(Length::Fill))
                .into()
        } else {
            Row::new()
                .spacing(14)
                .align_items(Alignment::Start)
                .width(Length::Fill)
                .push(avatar)
                .push(stack)
                .push(Space::with_width(Length::Fill))
                .into()
        }
    }
}

fn thinking_message_row<'a>(tick_counter: u32, compact: bool) -> Element<'a, Message> {
    let dots = match tick_counter % 4 {
        0 => "",
        1 => ".",
        2 => "..",
        _ => "...",
    };
    let avatar = container(text("N").size(18).style(CYAN))
        .padding(8)
        .style(chat_message_avatar_style);
    let bubble = container(
        Column::new()
            .spacing(10)
            .push(text(format!("Pensando{}", dots)).size(14).style(CYAN))
            .push(
                Row::new()
                    .spacing(6)
                    .push(container(Space::new(32, 6)).style(typing_skeleton_style))
                    .push(container(Space::new(52, 6)).style(typing_skeleton_style))
                    .push(container(Space::new(24, 6)).style(typing_skeleton_style)),
            ),
    )
    .padding([14, 18])
    .width(if compact {
        Length::Fill
    } else {
        Length::Fixed(480.0)
    })
    .style(progress_bubble_modern);

    Row::new()
        .spacing(14)
        .align_items(Alignment::Start)
        .width(Length::Fill)
        .push(avatar)
        .push(bubble)
        .push(if compact {
            Space::new(0, 0)
        } else {
            Space::with_width(Length::Fill)
        })
        .into()
}

fn current_time() -> String {
    chrono::Local::now().format("%H:%M").to_string()
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

#[derive(Debug, Clone, Copy)]
struct IconSvgStyle {
    color: Color,
}

impl svg::StyleSheet for IconSvgStyle {
    type Style = Theme;

    fn appearance(&self, _style: &Self::Style) -> svg::Appearance {
        svg::Appearance {
            color: Some(self.color),
        }
    }

    fn hovered(&self, _style: &Self::Style) -> svg::Appearance {
        svg::Appearance {
            color: Some(self.color),
        }
    }
}

#[derive(Debug, Clone, Copy)]
enum IconButtonKind {
    Primary,
    Subtle,
    Flat,
}

#[derive(Debug, Clone, Copy)]
struct IconButtonStyle {
    kind: IconButtonKind,
    size: f32,
    icon_size: u16,
    padding: [u16; 2],
}

impl IconButtonStyle {
    fn primary(size: f32, icon_size: u16) -> Self {
        Self {
            kind: IconButtonKind::Primary,
            size,
            icon_size,
            padding: [10, 12],
        }
    }

    fn subtle(size: f32, icon_size: u16) -> Self {
        Self {
            kind: IconButtonKind::Subtle,
            size,
            icon_size,
            padding: [10, 12],
        }
    }

    fn flat(size: f32, icon_size: u16) -> Self {
        Self {
            kind: IconButtonKind::Flat,
            size,
            icon_size,
            padding: [8, 10],
        }
    }

    fn icon_color(self) -> Color {
        match self.kind {
            IconButtonKind::Primary => TEXT_PRIMARY,
            IconButtonKind::Subtle => TEXT_SECONDARY,
            IconButtonKind::Flat => CYAN,
        }
    }
}

impl button::StyleSheet for IconButtonStyle {
    type Style = Theme;

    fn active(&self, _style: &Self::Style) -> button::Appearance {
        match self.kind {
            IconButtonKind::Primary => button::Appearance {
                background: Some(Color::from_rgb(0.160, 0.760, 0.840).into()),
                text_color: TEXT_PRIMARY,
                border: Border {
                    color: Color::from_rgb(0.250, 0.900, 0.980),
                    width: 1.0,
                    radius: 100.0.into(),
                },
                ..Default::default()
            },
            IconButtonKind::Subtle => button::Appearance {
                background: Some(Color::from_rgb(0.025, 0.034, 0.046).into()),
                text_color: TEXT_SECONDARY,
                border: Border {
                    color: Color::from_rgb(0.090, 0.120, 0.150),
                    width: 1.0,
                    radius: 100.0.into(),
                },
                ..Default::default()
            },
            IconButtonKind::Flat => button::Appearance {
                background: Some(Color::TRANSPARENT.into()),
                text_color: CYAN,
                border: Border {
                    color: Color::TRANSPARENT,
                    width: 1.0,
                    radius: 100.0.into(),
                },
                ..Default::default()
            },
        }
    }

    fn hovered(&self, _style: &Self::Style) -> button::Appearance {
        match self.kind {
            IconButtonKind::Primary => button::Appearance {
                background: Some(Color::from_rgb(0.210, 0.850, 0.920).into()),
                text_color: TEXT_PRIMARY,
                border: Border {
                    color: Color::from_rgb(0.500, 0.960, 1.000),
                    width: 1.0,
                    radius: 100.0.into(),
                },
                ..Default::default()
            },
            IconButtonKind::Subtle | IconButtonKind::Flat => button::Appearance {
                background: Some(Color::from_rgb(0.036, 0.056, 0.070).into()),
                text_color: CYAN,
                border: Border {
                    color: Color::from_rgb(0.070, 0.220, 0.260),
                    width: 1.0,
                    radius: 100.0.into(),
                },
                ..Default::default()
            },
        }
    }

    fn disabled(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.070, 0.110, 0.125).into()),
            text_color: TEXT_MUTED,
            border: Border {
                color: Color::from_rgb(0.110, 0.170, 0.190),
                width: 1.0,
                radius: 100.0.into(),
            },
            ..Default::default()
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct SidebarButtonStyle {
    active: bool,
}

impl button::StyleSheet for SidebarButtonStyle {
    type Style = Theme;

    fn active(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(
                if self.active {
                    Color::from_rgb(0.020, 0.060, 0.075)
                } else {
                    Color::TRANSPARENT
                }
                .into(),
            ),
            text_color: if self.active {
                TEXT_PRIMARY
            } else {
                TEXT_SECONDARY
            },
            border: Border {
                color: if self.active {
                    Color::from_rgb(0.050, 0.310, 0.365)
                } else {
                    Color::TRANSPARENT
                },
                width: 1.0,
                radius: 8.0.into(),
            },
            ..Default::default()
        }
    }

    fn hovered(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.018, 0.050, 0.064).into()),
            text_color: TEXT_PRIMARY,
            border: Border {
                color: Color::from_rgb(0.040, 0.230, 0.280),
                width: 1.0,
                radius: 8.0.into(),
            },
            ..Default::default()
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct PrimaryActionButtonStyle;

impl button::StyleSheet for PrimaryActionButtonStyle {
    type Style = Theme;

    fn active(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(ACCENT.into()),
            text_color: Color::WHITE,
            border: Border {
                color: Color::from_rgb(0.34, 0.65, 1.0),
                width: 1.0,
                radius: 7.0.into(),
            },
            ..Default::default()
        }
    }

    fn hovered(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.27, 0.62, 1.0).into()),
            text_color: Color::WHITE,
            border: Border {
                color: Color::from_rgb(0.50, 0.76, 1.0),
                width: 1.0,
                radius: 7.0.into(),
            },
            ..Default::default()
        }
    }

    fn disabled(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.065, 0.080, 0.100).into()),
            text_color: TEXT_MUTED,
            border: Border {
                color: Color::from_rgb(0.100, 0.125, 0.155),
                width: 1.0,
                radius: 7.0.into(),
            },
            ..Default::default()
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct SuggestionButtonStyle;

impl button::StyleSheet for SuggestionButtonStyle {
    type Style = Theme;

    fn active(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.036, 0.048, 0.064).into()),
            text_color: TEXT_PRIMARY,
            border: Border {
                color: Color::from_rgb(0.080, 0.125, 0.160),
                width: 1.0,
                radius: 8.0.into(),
            },
            ..Default::default()
        }
    }

    fn hovered(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.045, 0.064, 0.082).into()),
            text_color: TEXT_PRIMARY,
            border: Border {
                color: Color::from_rgb(0.075, 0.340, 0.395),
                width: 1.0,
                radius: 8.0.into(),
            },
            ..Default::default()
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct RoundSendButtonStyle;

impl button::StyleSheet for RoundSendButtonStyle {
    type Style = Theme;

    fn active(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.160, 0.760, 0.840).into()),
            text_color: Color::WHITE,
            border: Border {
                color: Color::from_rgb(0.250, 0.900, 0.980),
                width: 1.0,
                radius: 100.0.into(),
            },
            ..Default::default()
        }
    }

    fn hovered(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.210, 0.850, 0.920).into()),
            text_color: Color::WHITE,
            border: Border {
                color: Color::from_rgb(0.500, 0.960, 1.000),
                width: 1.0,
                radius: 100.0.into(),
            },
            ..Default::default()
        }
    }

    fn disabled(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.070, 0.110, 0.125).into()),
            text_color: TEXT_MUTED,
            border: Border {
                color: Color::from_rgb(0.110, 0.170, 0.190),
                width: 1.0,
                radius: 100.0.into(),
            },
            ..Default::default()
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct PremiumTogglerStyle;

impl toggler::StyleSheet for PremiumTogglerStyle {
    type Style = Theme;

    fn active(&self, _style: &Self::Style, is_active: bool) -> toggler::Appearance {
        toggler::Appearance {
            background: if is_active {
                Color::from_rgb(0.070, 0.330, 0.380)
            } else {
                Color::from_rgb(0.040, 0.052, 0.070)
            },
            background_border_width: 1.0,
            background_border_color: if is_active {
                Color::from_rgb(0.120, 0.560, 0.640)
            } else {
                Color::from_rgb(0.090, 0.120, 0.150)
            },
            foreground: if is_active { CYAN } else { TEXT_SECONDARY },
            foreground_border_width: 0.0,
            foreground_border_color: Color::TRANSPARENT,
        }
    }

    fn hovered(&self, style: &Self::Style, is_active: bool) -> toggler::Appearance {
        let mut appearance = self.active(style, is_active);
        appearance.background = if is_active {
            Color::from_rgb(0.085, 0.390, 0.440)
        } else {
            Color::from_rgb(0.052, 0.070, 0.090)
        };
        appearance
    }
}

#[derive(Debug, Clone, Copy)]
struct SubtleButtonStyle;

impl button::StyleSheet for SubtleButtonStyle {
    type Style = Theme;

    fn active(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.040, 0.058, 0.078).into()),
            text_color: TEXT_PRIMARY,
            border: Border {
                color: Color::from_rgb(0.100, 0.145, 0.185),
                width: 1.0,
                radius: 100.0.into(),
            },
            ..Default::default()
        }
    }

    fn hovered(&self, _style: &Self::Style) -> button::Appearance {
        button::Appearance {
            background: Some(Color::from_rgb(0.050, 0.078, 0.098).into()),
            text_color: CYAN,
            border: Border {
                color: Color::from_rgb(0.085, 0.270, 0.315),
                width: 1.0,
                radius: 100.0.into(),
            },
            ..Default::default()
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct ChatTextInputStyle;

impl iced::widget::text_input::StyleSheet for ChatTextInputStyle {
    type Style = Theme;

    fn active(&self, _style: &Self::Style) -> iced::widget::text_input::Appearance {
        chat_text_input_appearance(Color::TRANSPARENT)
    }

    fn focused(&self, _style: &Self::Style) -> iced::widget::text_input::Appearance {
        chat_text_input_appearance(Color::from_rgb(0.030, 0.130, 0.155))
    }

    fn placeholder_color(&self, _style: &Self::Style) -> Color {
        TEXT_MUTED
    }

    fn value_color(&self, _style: &Self::Style) -> Color {
        TEXT_PRIMARY
    }

    fn disabled_color(&self, _style: &Self::Style) -> Color {
        TEXT_MUTED
    }

    fn selection_color(&self, _style: &Self::Style) -> Color {
        Color::from_rgb(0.060, 0.300, 0.360)
    }

    fn disabled(&self, _style: &Self::Style) -> iced::widget::text_input::Appearance {
        chat_text_input_appearance(Color::TRANSPARENT)
    }
}

fn chat_text_input_appearance(border_color: Color) -> iced::widget::text_input::Appearance {
    iced::widget::text_input::Appearance {
        background: Color::TRANSPARENT.into(),
        border: Border {
            color: border_color,
            width: if border_color == Color::TRANSPARENT {
                0.0
            } else {
                1.0
            },
            radius: 8.0.into(),
        },
        icon_color: TEXT_MUTED,
    }
}

fn app_shell_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(BG.into()),
        text_color: Some(TEXT_PRIMARY),
        ..Default::default()
    }
}

fn chat_top_bar_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.006, 0.012, 0.020).into()),
        text_color: Some(TEXT_PRIMARY),
        ..Default::default()
    }
}

fn chat_status_pill_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.040, 0.052, 0.070).into()),
        border: Border {
            color: Color::from_rgb(0.080, 0.120, 0.155),
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn tooltip_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.036, 0.048, 0.066).into()),
        text_color: Some(TEXT_PRIMARY),
        border: Border {
            color: Color::from_rgb(0.090, 0.135, 0.175),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn user_avatar_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.060, 0.155, 0.245).into()),
        border: Border {
            color: Color::from_rgb(0.080, 0.190, 0.290),
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn chat_workspace_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.004, 0.010, 0.018).into()),
        text_color: Some(TEXT_PRIMARY),
        ..Default::default()
    }
}

fn chat_logo_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.010, 0.050, 0.070).into()),
        border: Border {
            color: Color::from_rgb(0.030, 0.690, 0.790),
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn prompt_icon_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.020, 0.120, 0.145).into()),
        border: Border {
            color: Color::from_rgb(0.035, 0.190, 0.225),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn chat_input_shell_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.040, 0.052, 0.068).into()),
        border: Border {
            color: Color::from_rgb(0.125, 0.160, 0.195),
            width: 1.0,
            radius: 28.0.into(),
        },
        ..Default::default()
    }
}

fn chat_attachment_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.025, 0.034, 0.046).into()),
        border: Border {
            color: Color::from_rgb(0.090, 0.120, 0.150),
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn chat_message_avatar_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.020, 0.075, 0.115).into()),
        border: Border {
            color: Color::from_rgb(0.030, 0.380, 0.620),
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn sidebar_learn_more_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.045, 0.058, 0.074).into()),
        border: Border {
            color: Color::from_rgb(0.085, 0.120, 0.150),
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn premium_surface_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.026, 0.038, 0.064).into()),
        border: Border {
            color: Color::from_rgb(0.075, 0.115, 0.155),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn settings_dot_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(CYAN.into()),
        border: Border {
            color: Color::from_rgb(0.110, 0.460, 0.520),
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn typing_skeleton_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.110, 0.145, 0.175).into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
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
        background: Some(Color::from_rgb(0.048, 0.062, 0.082).into()),
        border: Border {
            color: Color::from_rgb(0.120, 0.165, 0.210),
            width: 1.0,
            radius: [8.0, 8.0, 8.0, 2.0].into(),
        },
        ..Default::default()
    }
}
fn operator_bubble_modern(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(PETROL.into()),
        border: Border {
            color: Color::from_rgb(0.020, 0.320, 0.385),
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
        background: Some(Color::from_rgb(0.030, 0.055, 0.070).into()),
        border: Border {
            color: Color::from_rgb(0.060, 0.310, 0.370),
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
        background: Some(Color::from_rgb(0.045, 0.058, 0.073).into()),
        border: Border {
            color: Color::from_rgb(0.12, 0.17, 0.21),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn section_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.014, 0.026, 0.038).into()),
        border: Border {
            color: Color::from_rgb(0.070, 0.115, 0.155),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn hud_panel_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.012, 0.020, 0.026).into()),
        border: Border {
            color: Color::from_rgb(0.045, 0.115, 0.145),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn hud_tile_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.016, 0.028, 0.036).into()),
        border: Border {
            color: Color::from_rgb(0.040, 0.105, 0.130),
            width: 1.0,
            radius: 4.0.into(),
        },
        ..Default::default()
    }
}

fn hud_core_stage_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.005, 0.012, 0.020).into()),
        border: Border {
            color: Color::from_rgb(0.035, 0.120, 0.160),
            width: 1.0,
            radius: 4.0.into(),
        },
        ..Default::default()
    }
}

fn nexus_core_ring_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.008, 0.024, 0.036).into()),
        border: Border {
            color: Color::from_rgb(0.115, 0.560, 0.680),
            width: 1.0,
            radius: 200.0.into(),
        },
        ..Default::default()
    }
}

fn nexus_core_inner_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.014, 0.060, 0.092).into()),
        border: Border {
            color: Color::from_rgb(0.220, 0.720, 0.850),
            width: 1.0,
            radius: 120.0.into(),
        },
        ..Default::default()
    }
}

fn hud_orbit_chip_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.012, 0.030, 0.040).into()),
        border: Border {
            color: Color::from_rgb(0.055, 0.150, 0.180),
            width: 1.0,
            radius: 4.0.into(),
        },
        ..Default::default()
    }
}

fn hud_glass_strip_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.012, 0.030, 0.040).into()),
        border: Border {
            color: Color::from_rgb(0.065, 0.235, 0.305),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn nexus_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.014, 0.026, 0.038).into()),
        border: Border {
            color: Color::from_rgb(0.070, 0.115, 0.155),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn nexus_main_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.012, 0.040, 0.052).into()),
        border: Border {
            color: Color::from_rgb(0.035, 0.190, 0.230),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn nexus_active_pill_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.016, 0.095, 0.070).into()),
        border: Border {
            color: Color::from_rgb(0.050, 0.210, 0.160),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn nexus_status_icon_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.010, 0.070, 0.085).into()),
        border: Border {
            color: Color::from_rgb(0.050, 0.520, 0.610),
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn nexus_metric_icon_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.018, 0.056, 0.082).into()),
        border: Border {
            color: Color::from_rgb(0.040, 0.120, 0.165),
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn nexus_update_icon_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.026, 0.046, 0.060).into()),
        border: Border {
            color: Color::from_rgb(0.055, 0.105, 0.135),
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn nexus_chat_empty_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.010, 0.020, 0.032).into()),
        border: Border {
            color: Color::from_rgb(0.052, 0.088, 0.120),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn vertical_divider_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.080, 0.125, 0.155).into()),
        ..Default::default()
    }
}

fn platform_strip_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.035, 0.052, 0.064).into()),
        border: Border {
            color: ACCENT_SOFT,
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn overview_chip_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.050, 0.064, 0.078).into()),
        border: Border {
            color: Color::from_rgb(0.105, 0.150, 0.185),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn role_summary_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.040, 0.052, 0.066).into()),
        border: Border {
            color: Color::from_rgb(0.095, 0.135, 0.170),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn hero_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.035, 0.055, 0.070).into()),
        border: Border {
            color: Color::from_rgb(0.11, 0.25, 0.34),
            width: 1.0,
            radius: 10.0.into(),
        },
        ..Default::default()
    }
}

fn simple_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.042, 0.054, 0.068).into()),
        border: Border {
            color: Color::from_rgb(0.090, 0.125, 0.160),
            width: 1.0,
            radius: 9.0.into(),
        },
        ..Default::default()
    }
}

fn flow_node_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.043, 0.061, 0.078).into()),
        border: Border {
            color: Color::from_rgb(0.10, 0.24, 0.32),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn active_flow_node_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.040, 0.088, 0.102).into()),
        border: Border {
            color: Color::from_rgb(0.24, 0.74, 0.88),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn task_row_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.018, 0.032, 0.044).into()),
        border: Border {
            color: Color::from_rgb(0.055, 0.095, 0.125),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn incident_row_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.075, 0.05, 0.06).into()),
        border: Border {
            color: Color::from_rgb(0.22, 0.1, 0.12),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn summary_banner_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.04, 0.07, 0.08).into()),
        border: Border {
            color: Color::from_rgb(0.16, 0.30, 0.34),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn technical_block_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.035, 0.045, 0.055).into()),
        border: Border {
            color: Color::from_rgb(0.09, 0.12, 0.15),
            width: 1.0,
            radius: 5.0.into(),
        },
        ..Default::default()
    }
}

fn empty_state_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.04, 0.052, 0.066).into()),
        border: Border {
            color: Color::from_rgb(0.10, 0.14, 0.18),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn log_block_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.025, 0.034, 0.044).into()),
        border: Border {
            color: Color::from_rgb(0.10, 0.16, 0.20),
            width: 1.0,
            radius: 5.0.into(),
        },
        ..Default::default()
    }
}

fn header_chip_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.018, 0.028, 0.046).into()),
        border: Border {
            color: Color::from_rgb(0.075, 0.120, 0.190),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn brand_mark_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.006, 0.045, 0.060).into()),
        border: Border {
            color: Color::from_rgb(0.020, 0.700, 0.780),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn mission_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.018, 0.032, 0.082).into()),
        border: Border {
            color: Color::from_rgb(0.130, 0.245, 0.545),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn mission_meta_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.024, 0.040, 0.074).into()),
        border: Border {
            color: Color::from_rgb(0.090, 0.150, 0.260),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn orb_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.030, 0.120, 0.335).into()),
        border: Border {
            color: Color::from_rgb(0.180, 0.500, 1.000),
            width: 2.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn ai_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.035, 0.055, 0.078).into()),
        border: Border {
            color: Color::from_rgb(0.105, 0.165, 0.235),
            width: 1.0,
            radius: 7.0.into(),
        },
        ..Default::default()
    }
}

fn mode_banner_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.044, 0.048, 0.092).into()),
        border: Border {
            color: Color::from_rgb(0.180, 0.125, 0.330),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn agent_avatar_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.060, 0.170, 0.330).into()),
        border: Border {
            color: ACCENT,
            width: 1.0,
            radius: 100.0.into(),
        },
        ..Default::default()
    }
}

fn success_shield_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.060, 0.360, 0.180).into()),
        border: Border {
            color: SUCCESS,
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn feedback_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.030, 0.045, 0.070).into()),
        border: Border {
            color: Color::from_rgb(0.110, 0.220, 0.360),
            width: 1.0,
            radius: 6.0.into(),
        },
        ..Default::default()
    }
}

fn header_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.005, 0.012, 0.020).into()),
        ..Default::default()
    }
}

fn panel_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.026, 0.034, 0.043).into()),
        ..Default::default()
    }
}

fn panel_center_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.004, 0.010, 0.018).into()),
        ..Default::default()
    }
}

fn sidebar_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.006, 0.012, 0.020).into()),
        border: Border {
            color: Color::from_rgb(0.060, 0.085, 0.110),
            width: 1.0,
            radius: 0.0.into(),
        },
        ..Default::default()
    }
}

fn sidebar_item_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::TRANSPARENT.into()),
        border: Border {
            color: Color::TRANSPARENT,
            width: 1.0,
            radius: 7.0.into(),
        },
        ..Default::default()
    }
}

fn sidebar_item_active_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.028, 0.052, 0.066).into()),
        border: Border {
            color: Color::from_rgb(0.035, 0.250, 0.300),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn sidebar_card_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.035, 0.046, 0.060).into()),
        border: Border {
            color: Color::from_rgb(0.085, 0.120, 0.150),
            width: 1.0,
            radius: 8.0.into(),
        },
        ..Default::default()
    }
}

fn meter_track_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(Color::from_rgb(0.065, 0.080, 0.096).into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}

fn meter_fill_success_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(SUCCESS.into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}

fn meter_fill_accent_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(ACCENT.into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}

fn meter_fill_warning_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        background: Some(WARNING.into()),
        border: Border {
            radius: 100.0.into(),
            ..Default::default()
        },
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
        commands: payload.commands,
        runtime_events: payload.runtime_events,
        verifications: payload.verifications,
        org_events: payload.org_events,
        swarm: payload.swarm,
        incidents: payload.incidents,
        observations: payload.observations,
        memory_entries: payload.memory_entries,
        updated_at: Some(current_time()),
        error: None,
    })
}

async fn load_product_status() -> Result<ProductStatus, String> {
    run_product_json::<ProductStatus>(&["status"]).await
}

async fn run_product_json<T: DeserializeOwned>(args: &[&str]) -> Result<T, String> {
    let root = project_root();
    let local_bin = root.join("bin").join("nexus");
    let bin = if local_bin.exists() {
        local_bin
    } else {
        PathBuf::from("/usr/bin/nexus")
    };
    let output = TokioCommand::new(&bin)
        .args(args)
        .current_dir(&root)
        .output()
        .await
        .map_err(|error| format!("{}: {}", bin.display(), error))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let detail = if !stderr.is_empty() { stderr } else { stdout };
        return Err(format!("nexus {} falhou: {}", args.join(" "), detail));
    }

    serde_json::from_slice(&output.stdout)
        .map_err(|error| format!("json invalido em nexus {}: {}", args.join(" "), error))
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
    feedback: Option<ChatFeedback>,
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

async fn reply_approval(command_id: String, approve: bool) -> Result<String, String> {
    let client = reqwest::Client::new();
    let url = if approve {
        "http://127.0.0.1:4000/api/approve"
    } else {
        "http://127.0.0.1:4000/api/deny"
    };

    let payload = serde_json::json!({
        "command_id": command_id
    });

    let res = client
        .post(url)
        .json(&payload)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if res.status().is_success() {
        Ok("Approval Sent".to_string())
    } else {
        Err("Failed to send approval".to_string())
    }
}

fn chat_msg_terminal_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        text_color: Some(Color::from_rgb(0.5, 1.0, 0.5)),
        background: Some(Color::from_rgb(0.05, 0.05, 0.05).into()),
        border: Border {
            color: Color::from_rgb(0.2, 0.4, 0.2),
            width: 1.0,
            radius: 4.0.into(),
        },
        shadow: iced::Shadow::default(),
    }
}

fn chat_msg_evidence_style(_theme: &Theme) -> container::Appearance {
    container::Appearance {
        text_color: Some(Color::from_rgb(0.9, 0.9, 1.0)),
        background: Some(Color::from_rgb(0.08, 0.12, 0.20).into()),
        border: Border {
            color: Color::from_rgb(0.3, 0.5, 0.8),
            width: 1.0,
            radius: 6.0.into(),
        },
        shadow: iced::Shadow::default(),
    }
}
