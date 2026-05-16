package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

const refreshEvery = 2 * time.Second

var (
	titleStyle = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("86"))
	mutedStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("245"))
	errorStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("203"))
	okStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("114"))
	warnStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("220"))
	tabStyle   = lipgloss.NewStyle().Padding(0, 1)
	activeTabStyle = lipgloss.NewStyle().
		Padding(0, 1).
		Bold(true).
		Foreground(lipgloss.Color("16")).
		Background(lipgloss.Color("86"))
	panelStyle = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).Padding(1, 2)
)

type model struct {
	root      string
	python    string
	tab       int
	width     int
	height    int
	spinner   spinner.Model
	loading   bool
	err       error
	updatedAt time.Time
	data      dashboardData
}

type dashboardData struct {
	Status        map[string]any
	MemoryStatus  map[string]any
	AgentTicks    []map[string]any
	Approvals     []map[string]any
	RuntimeEvents []map[string]any
	Verifications []map[string]any
	Observations  []map[string]any
	SwarmStatus   map[string]any
	Incidents     []map[string]any
}

type tickMsg time.Time
type loadedMsg struct {
	data dashboardData
	err  error
}

func main() {
	root, err := findRepoRoot()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	s := spinner.New()
	s.Spinner = spinner.Dot
	m := model{
		root:    root,
		python:  resolvePython(root),
		spinner: s,
		loading: true,
	}

	if _, err := tea.NewProgram(m, tea.WithAltScreen()).Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func (m model) Init() tea.Cmd {
	return tea.Batch(m.spinner.Tick, loadDashboard(m.root, m.python), tick())
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "q", "ctrl+c", "esc":
			return m, tea.Quit
		case "right", "l", "tab":
			m.tab = (m.tab + 1) % len(tabs)
		case "left", "h", "shift+tab":
			m.tab--
			if m.tab < 0 {
				m.tab = len(tabs) - 1
			}
		case "r":
			m.loading = true
			return m, loadDashboard(m.root, m.python)
		}
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd
	case tickMsg:
		m.loading = true
		return m, tea.Batch(loadDashboard(m.root, m.python), tick())
	case loadedMsg:
		m.loading = false
		m.err = msg.err
		if msg.err == nil {
			m.data = msg.data
			m.updatedAt = time.Now()
		}
	}
	return m, nil
}

var tabs = []string{"Overview", "Swarm", "Agents", "Approvals", "Runtime", "Verification", "Incidents"}

func (m model) View() string {
	var b strings.Builder
	b.WriteString(titleStyle.Render("NEXUS Cognitive Company TUI"))
	b.WriteString(" ")
	if m.loading {
		b.WriteString(m.spinner.View())
		b.WriteString(" refreshing")
	} else if !m.updatedAt.IsZero() {
		b.WriteString(mutedStyle.Render("updated " + m.updatedAt.Format("15:04:05")))
	}
	b.WriteString("\n")
	b.WriteString(m.renderTabs())
	b.WriteString("\n\n")

	if m.err != nil {
		b.WriteString(errorStyle.Render("Data source error: " + m.err.Error()))
		b.WriteString("\n\n")
	}

	content := ""
	switch tabs[m.tab] {
	case "Overview":
		content = m.viewOverview()
	case "Swarm":
		content = m.viewSwarm()
	case "Agents":
		content = m.viewAgents()
	case "Approvals":
		content = m.viewApprovals()
	case "Runtime":
		content = m.viewRuntimeEvents()
	case "Verification":
		content = m.viewVerifications()
	case "Incidents":
		content = m.viewIncidents()
	}
	b.WriteString(panelStyle.Width(max(40, m.width-6)).Render(content))
	b.WriteString("\n\n")
	b.WriteString(mutedStyle.Render("keys: h/l or arrows switch view · r refresh · q quit"))
	return b.String()
}

func (m model) renderTabs() string {
	parts := make([]string, 0, len(tabs))
	for i, tab := range tabs {
		if i == m.tab {
			parts = append(parts, activeTabStyle.Render(tab))
		} else {
			parts = append(parts, tabStyle.Render(tab))
		}
	}
	return strings.Join(parts, " ")
}

func (m model) viewOverview() string {
	status := m.data.Status
	memory := m.data.MemoryStatus
	lines := []string{
		titleStyle.Render("Daemon"),
		fmt.Sprintf("status: %s", value(status, "status")),
		fmt.Sprintf("mode:   %s", value(status, "mode")),
		fmt.Sprintf("agents: %s", value(status, "agents")),
		fmt.Sprintf("tasks:  %s", value(status, "tasks")),
		"",
		titleStyle.Render("Memory"),
		fmt.Sprintf("tasks=%s decisions=%s events=%s summaries=%s", value(memory, "tasks"), value(memory, "decisions"), value(memory, "events"), value(memory, "summaries")),
		fmt.Sprintf("runtime_events=%s verifications=%s observations=%s agent_ticks=%s", value(memory, "runtime_events"), value(memory, "verifications"), value(memory, "observations"), value(memory, "agent_ticks")),
	}
	return strings.Join(lines, "\n")
}

func (m model) viewAgents() string {
	if len(m.data.AgentTicks) == 0 {
		return mutedStyle.Render("No agent ticks recorded yet. Run `./bin/nexus org tick-agents` or start the org daemon.")
	}
	var lines []string
	for _, item := range m.data.AgentTicks {
		lines = append(lines, fmt.Sprintf("%-10s %-10s %-10s %s",
			value(item, "agent_role"),
			value(item, "mode"),
			statusText(value(item, "status")),
			value(item, "summary"),
		))
	}
	return strings.Join(lines, "\n")
}

func (m model) viewApprovals() string {
	if len(m.data.Approvals) == 0 {
		return okStyle.Render("No pending approvals.")
	}
	var lines []string
	for _, item := range m.data.Approvals {
		lines = append(lines, fmt.Sprintf("%s %s risk=%s status=%s",
			value(item, "proposal_id"),
			value(item, "command"),
			value(item, "risk_level"),
			statusText(value(item, "status")),
		))
	}
	return strings.Join(lines, "\n")
}

func (m model) viewRuntimeEvents() string {
	if len(m.data.RuntimeEvents) == 0 {
		return mutedStyle.Render("No runtime events yet.")
	}
	var lines []string
	for _, item := range m.data.RuntimeEvents {
		lines = append(lines, fmt.Sprintf("%s %-18s %-8s %s",
			short(value(item, "command_id")),
			value(item, "event_type"),
			value(item, "stream"),
			value(item, "created_at"),
		))
	}
	return strings.Join(lines, "\n")
}

func (m model) viewVerifications() string {
	if len(m.data.Verifications) == 0 {
		return mutedStyle.Render("No verification records yet.")
	}
	var lines []string
	for _, item := range m.data.Verifications {
		lines = append(lines, fmt.Sprintf("%s %-10s %-8s %s",
			short(value(item, "command_id")),
			value(item, "target_type"),
			statusText(value(item, "status")),
			value(item, "target"),
		))
	}
	return strings.Join(lines, "\n")
}

func (m model) viewObservations() string {
	if len(m.data.Observations) == 0 {
		return mutedStyle.Render("No observations yet.")
	}
	var lines []string
	for _, item := range m.data.Observations {
		lines = append(lines, fmt.Sprintf("%-12s confidence=%s window=%s",
			value(item, "mode"),
			value(item, "confidence"),
			value(item, "active_window"),
		))
	}
	return strings.Join(lines, "\n")
}

func (m model) viewSwarm() string {
	swarm := m.data.SwarmStatus
	if swarm == nil || value(swarm, "current_goal") == "-" {
		return mutedStyle.Render("No active Swarm goal. Submit one via `./bin/nexus org swarm-submit`")
	}

	var b strings.Builder
	b.WriteString(fmt.Sprintf("%s %s\n\n", titleStyle.Render("Objective:"), value(swarm, "current_goal")))

	b.WriteString(titleStyle.Render("Plan Execution") + "\n")
	if plan, ok := swarm["plan"].([]any); ok && len(plan) > 0 {
		for _, p := range plan {
			item := p.(map[string]any)
			b.WriteString(fmt.Sprintf("%-12s %-30s %s\n",
				value(item, "role"),
				value(item, "task"),
				statusText(value(item, "status")),
			))
		}
	} else {
		b.WriteString(mutedStyle.Render("No plan items yet.") + "\n")
	}

	b.WriteString("\n" + titleStyle.Render("Agent Status") + "\n")
	if agents, ok := swarm["agents"].([]any); ok && len(agents) > 0 {
		for _, a := range agents {
			agent := a.(map[string]any)
			b.WriteString(fmt.Sprintf("%-12s %-12s conf=%-4s risk=%s\n",
				value(agent, "role"),
				statusText(value(agent, "status")),
				value(agent, "confidence"),
				value(agent, "risk_level"),
			))
		}
	}

	return b.String()
}

func (m model) viewIncidents() string {
	if len(m.data.Incidents) == 0 {
		return okStyle.Render("No incidents reported.")
	}
	var lines []string
	for _, item := range m.data.Incidents {
		lines = append(lines, fmt.Sprintf("%-8s %-12s %s",
			statusText(value(item, "severity")),
			value(item, "module"),
			value(item, "message"),
		))
	}
	return strings.Join(lines, "\n")
}

func tick() tea.Cmd {
	return tea.Tick(refreshEvery, func(t time.Time) tea.Msg { return tickMsg(t) })
}

func loadDashboard(root, python string) tea.Cmd {
	return func() tea.Msg {
		data, err := fetchDashboard(root, python)
		return loadedMsg{data: data, err: err}
	}
}

func fetchDashboard(root, python string) (dashboardData, error) {
	var data dashboardData
	var errs []string

	if err := loadJSON(root, python, []string{"status"}, &data.Status); err != nil {
		errs = append(errs, err.Error())
	}
	if err := loadJSON(root, python, []string{"memory-status"}, &data.MemoryStatus); err != nil {
		errs = append(errs, err.Error())
	}
	if err := loadJSON(root, python, []string{"agent-ticks", "--limit", "12"}, &data.AgentTicks); err != nil {
		errs = append(errs, err.Error())
	}
	if err := loadJSON(root, python, []string{"approvals", "--status", "pending_approval"}, &data.Approvals); err != nil {
		errs = append(errs, err.Error())
	}
	if err := loadJSON(root, python, []string{"runtime-events", "--limit", "12"}, &data.RuntimeEvents); err != nil {
		errs = append(errs, err.Error())
	}
	if err := loadJSON(root, python, []string{"verifications", "--limit", "12"}, &data.Verifications); err != nil {
		errs = append(errs, err.Error())
	}
	if err := loadJSON(root, python, []string{"observations", "--limit", "12"}, &data.Observations); err != nil {
		errs = append(errs, err.Error())
	}
	if err := loadJSON(root, python, []string{"swarm-status"}, &data.SwarmStatus); err != nil {
		errs = append(errs, err.Error())
	}
	if err := loadJSON(root, python, []string{"incidents", "--limit", "12"}, &data.Incidents); err != nil {
		errs = append(errs, err.Error())
	}

	if len(errs) > 0 {
		return data, errors.New(strings.Join(errs, " | "))
	}
	return data, nil
}

func loadJSON(root, python string, args []string, out any) error {
	cmdArgs := append([]string{"-m", "nexus_core.organization"}, args...)
	cmd := exec.Command(python, cmdArgs...)
	cmd.Dir = root
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	raw, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("%s: %w %s", strings.Join(args, " "), err, strings.TrimSpace(stderr.String()))
	}
	if err := json.Unmarshal(raw, out); err != nil {
		return fmt.Errorf("%s: invalid JSON: %w", strings.Join(args, " "), err)
	}
	return nil
}

func findRepoRoot() (string, error) {
	dir, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		if _, err := os.Stat(filepath.Join(dir, "configs", "nexus.toml")); err == nil {
			return dir, nil
		}
		next := filepath.Dir(dir)
		if next == dir {
			return "", errors.New("could not find configs/nexus.toml; run from the NEXUS repository")
		}
		dir = next
	}
}

func resolvePython(root string) string {
	venv := filepath.Join(root, ".venv", "bin", "python")
	if _, err := os.Stat(venv); err == nil {
		return venv
	}
	return "python3"
}

func value(m map[string]any, key string) string {
	if m == nil {
		return "-"
	}
	v, ok := m[key]
	if !ok || v == nil {
		return "-"
	}
	return fmt.Sprint(v)
}

func statusText(s string) string {
	switch strings.ToLower(s) {
	case "passed", "executed", "online", "active", "observing", "recording", "guarding":
		return okStyle.Render(s)
	case "pending_approval", "approved", "standby":
		return warnStyle.Render(s)
	case "failed", "blocked", "error":
		return errorStyle.Render(s)
	default:
		return s
	}
}

func short(s string) string {
	if s == "" || s == "-" {
		return "-"
	}
	if len(s) <= 12 {
		return s
	}
	return s[:12]
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
