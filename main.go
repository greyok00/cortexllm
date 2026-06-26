package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/winder/bubblelayout"
)

// ═══════════════════════════════════════════════════════════════════════════════
// DATA STRUCTURES
// ═══════════════════════════════════════════════════════════════════════════════

type Message struct {
	Platform  string
	Content   string
	IsUser    bool
	Time      time.Time
	TokensIn  int
	TokensOut int
}

type MemoryEntry struct {
	Timestamp time.Time `json:"timestamp"`
	Role      string    `json:"role"`
	Content   string    `json:"content"`
	TokensIn  int       `json:"tokens_in"`
	TokensOut int       `json:"tokens_out"`
	Platform  string    `json:"platform"`
}

type UserProfile struct {
	Name               string
	PreferredModel     string
	CommonTopics       []string
	CommunicationStyle string
	KnownFacts         map[string]string
}

type Theme struct {
	Name      string
	SidebarBg string
	ChatBg    string
	Accent    string
	Text      string
	TextMuted string
	Border    string
}

// Palette stores multiple colors for rich theming
type Palette struct {
	Primary   string // Main accent color
	Secondary string // Secondary accent
	Tertiary  string // Third accent color
	BgDark    string // Darkest background
	BgMid     string // Mid background
	BgLight   string // Light background
	Text      string // Primary text
	TextDim   string // Dimmed text
	Success   string // Success states
	Warning   string // Warning states
	Error     string // Error states
	Highlight string // Highlights
}

type PlatformConfig struct {
	Enabled      bool   `json:"enabled"`
	Mode         string `json:"mode"`
	Endpoint     string `json:"endpoint,omitempty"`
	TokenEnv     string `json:"token_env,omitempty"`
	SessionPrefix string `json:"session_prefix,omitempty"`
}

type Config struct {
	OllamaKey string
	Brain     string // Primary reasoning model
	Hand      string // Task execution model
	// Platform models
	OpenCodeModel string         `json:"opencode_model"`
	OpenClawModel string         `json:"openclaw_model"`
	Platforms     map[string]PlatformConfig `json:"platforms"`
}

type MemoryCategory struct {
	Name        string
	Items       []string
	Color       string
	Icon        string
	Description string
	Type        string // "knowledge", "tasks", "patterns", "topics"
}

// AutoLearning tracks what the system has learned
type AutoLearning struct {
	Keywords    []string       // Extracted keywords from conversations
	TaskTypes   []string       // Types of tasks (coding, debugging, design)
	Patterns    []string       // Code patterns, workflows
	Topics      map[string]int // Topic frequency
	LastUpdated time.Time
}

type PlatformStatus struct {
	Name     string
	Online   bool
	LastPing time.Time
	Latency  int
	Model    string
}

type DiagnosticData struct {
	LatencyHistory []int
	TokenHistory   []int
	MaxPoints      int
}

type Worker struct {
	Name        string
	Status      string
	Type        string
	LastRun     time.Time
	Description string
}

// Theme defines a visual style for the interface
type RPGTheme struct {
	Name        string   // Theme name
	Description string   // Theme description
	Colors      Theme    // Legacy compatibility
	Palette     Palette  // Rich multi-color palette
	Icon        string   // Main icon
	AvatarSet   []string // Animated frames
	PlatformSet []string // Platform avatars
	StatusOn    string
	StatusOff   string
	Pattern     string // Background pattern type
}

// 7 Visual Themes with complementary two-tone backgrounds
var rpgThemes = []RPGTheme{
	{
		Name:        "Sovereign",
		Description: "Keeper of ancient wisdom, ruler of eternal sands",
		Colors:      Theme{"Sovereign", "#1A1612", "#2A2420", "#00A86B", "#F4E8C1", "#C9A961", "#8B7355"},
		Palette: Palette{
			Primary: "#00A86B", Secondary: "#C9A961", Tertiary: "#D4AF37",
			BgDark: "#0D0A08", BgMid: "#1A1612", BgLight: "#2A2420",
			Text: "#F4E8C1", TextDim: "#C9A961", Success: "#00A86B", Warning: "#D4AF37", Error: "#8B4513", Highlight: "#FFD700",
		},
		Icon:        "👑",
		AvatarSet:   []string{"👑", "👑 ", " 👑", "👑"},
		PlatformSet: []string{"◆", "◇", "◈"},
		StatusOn:    "●",
		StatusOff:   "○",
		Pattern:     "hieroglyph",
	},
	{
		Name:        "Shadow",
		Description: "Master of stealth, moving unseen through darkness",
		Colors:      Theme{"Shadow", "#0D0D0D", "#1A1A1A", "#8B0000", "#A0A0A0", "#4A4A4A", "#2A2A2A"},
		Palette: Palette{
			Primary: "#8B0000", Secondary: "#DC143C", Tertiary: "#4A4A4A",
			BgDark: "#050505", BgMid: "#0D0D0D", BgLight: "#1A1A1A",
			Text: "#E8E8E8", TextDim: "#808080", Success: "#32CD32", Warning: "#FFD700", Error: "#FF0000", Highlight: "#FF4500",
		},
		Icon:        "🥷",
		AvatarSet:   []string{"🥷", "🥷 ", " 🥷", "🥷"},
		PlatformSet: []string{"▪", "▫", "◾"},
		StatusOn:    "●",
		StatusOff:   "○",
		Pattern:     "shadow",
	},
	{
		Name:        "Netrunner",
		Description: "Ghost in the machine, bending code to will",
		Colors:      Theme{"Netrunner", "#000000", "#001100", "#00FF41", "#00FF41", "#008F11", "#003B00"},
		Palette: Palette{
			Primary: "#00FF41", Secondary: "#008F11", Tertiary: "#39FF14",
			BgDark: "#000000", BgMid: "#000800", BgLight: "#001100",
			Text: "#00FF41", TextDim: "#008F11", Success: "#00FF41", Warning: "#FFFF00", Error: "#FF0000", Highlight: "#7FFF00",
		},
		Icon:        "💻",
		AvatarSet:   []string{"💻", "💻 ", " 💻", "💻"},
		PlatformSet: []string{"►", "▶", "◄"},
		StatusOn:    "█",
		StatusOff:   "░",
		Pattern:     "matrix",
	},
	{
		Name:        "Aviator",
		Description: "Navigator of skies, commanding the open air",
		Colors:      Theme{"Aviator", "#0A1628", "#142540", "#FF6B00", "#E8F4F8", "#5A7A9A", "#2A4060"},
		Palette: Palette{
			Primary: "#FF6B00", Secondary: "#0077BE", Tertiary: "#87CEEB",
			BgDark: "#050A10", BgMid: "#0A1628", BgLight: "#142540",
			Text: "#E8F4F8", TextDim: "#5A7A9A", Success: "#00CED1", Warning: "#FFA500", Error: "#FF4500", Highlight: "#FFD700",
		},
		Icon:        "✈️",
		AvatarSet:   []string{"✈️", "✈️ ", " ✈️", "✈️"},
		PlatformSet: []string{"▲", "△", "◬"},
		StatusOn:    "●",
		StatusOff:   "○",
		Pattern:     "radar",
	},
	{
		Name:        "Aquanaut",
		Description: "Explorer of the deep, seeking ocean mysteries",
		Colors:      Theme{"Aquanaut", "#000510", "#001525", "#00FFFF", "#E0FFFF", "#008B8B", "#004040"},
		Palette: Palette{
			Primary: "#00FFFF", Secondary: "#008B8B", Tertiary: "#20B2AA",
			BgDark: "#000208", BgMid: "#000510", BgLight: "#001525",
			Text: "#E0FFFF", TextDim: "#008B8B", Success: "#00CED1", Warning: "#FFD700", Error: "#FF6B6B", Highlight: "#7FFFD4",
		},
		Icon:        "🤿",
		AvatarSet:   []string{"🤿", "🤿 ", " 🤿", "🤿"},
		PlatformSet: []string{"●", "◐", "◑"},
		StatusOn:    "●",
		StatusOff:   "○",
		Pattern:     "waves",
	},
	{
		Name:        "Industrialist",
		Description: "Baron of industry, architect of steam and steel",
		Colors:      Theme{"Industrialist", "#1A1510", "#2A2520", "#CD7F32", "#F5E6D3", "#8B6914", "#5A4A30"},
		Palette: Palette{
			Primary: "#CD7F32", Secondary: "#B8860B", Tertiary: "#DAA520",
			BgDark: "#0D0A08", BgMid: "#1A1510", BgLight: "#2A2520",
			Text: "#F5E6D3", TextDim: "#DEB887", Success: "#9ACD32", Warning: "#DAA520", Error: "#8B4513", Highlight: "#FFD700",
		},
		Icon:        "🎩",
		AvatarSet:   []string{"🎩", "🎩 ", " 🎩", "🎩"},
		PlatformSet: []string{"◆", "◈", "◇"},
		StatusOn:    "◆",
		StatusOff:   "◇",
		Pattern:     "gears",
	},
	{
		Name:        "Astronaut",
		Description: "Voyager of the void, exploring infinite cosmos",
		Colors:      Theme{"Astronaut", "#0B0D17", "#1A1D2E", "#FFFFFF", "#E8E8E8", "#7A8AA8", "#4A5568"},
		Palette: Palette{
			Primary: "#FFFFFF", Secondary: "#C0C0C0", Tertiary: "#A9A9A9",
			BgDark: "#05060B", BgMid: "#0B0D17", BgLight: "#1A1D2E",
			Text: "#FFFFFF", TextDim: "#808080", Success: "#00FF7F", Warning: "#FFA500", Error: "#FF4500", Highlight: "#87CEEB",
		},
		Icon:        "🚀",
		AvatarSet:   []string{"🚀", "🚀 ", " 🚀", "🚀"},
		PlatformSet: []string{"★", "☆", "✦"},
		StatusOn:    "●",
		StatusOff:   "○",
		Pattern:     "stars",
	},
}

// Keep old themes array for compatibility (maps to rpgThemes[themeIndex].Colors)
var themes = []Theme{
	rpgThemes[0].Colors,
	rpgThemes[1].Colors,
	rpgThemes[2].Colors,
	rpgThemes[3].Colors,
	rpgThemes[4].Colors,
	rpgThemes[5].Colors,
	rpgThemes[6].Colors,
}

// Helper to safely get theme count
func getThemeCount() int {
	return len(rpgThemes)
}

var avatarFrames = map[string][]string{
	"opencode": {"◆", "◇", "◈", "◇"},
	"openclaw": {"◈", "◉", "◆", "◉"},
}

var blockChars = []string{"▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"}
var waveChars = []string{"▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"}

// ═══════════════════════════════════════════════════════════════════════════════
// BACKGROUND PATTERNS - Theme-specific wallpapers
// ═══════════════════════════════════════════════════════════════════════════════

// PatternChars contains characters for different patterns
var patternChars = map[string][]string{
	"hieroglyph": {"𓀀", "𓀁", "𓀂", "𓀃", "𓀄", "𓀅", "𓀆", "𓀇"},
	"shadow":     {"░", "▒", "▓", "█", "▀", "▄", "▌", "▐"},
	"matrix":     {"0", "1", "░", "▒", "▓", "█", "│", "─"},
	"radar":      {"◯", "◉", "◎", "◍", "◈", "◇", "◆", "◊"},
	"bamboo":     {"┃", "━", "┏", "┓", "┗", "┛", "┣", "┫"},
	"waves":      {"~", "≈", "≋", "∿", "〰", "～", "〜", "▁"},
	"gears":      {"⚙", "⚛", "⚛", "⚙", "⚜", "⚘", "⚚", "⚔"},
	"stars":      {"✦", "✧", "✩", "✪", "✫", "✬", "✭", "✮"},
}

// generatePattern creates a background pattern for the sidebar/diagnostics
func generatePattern(patternType string, width, height int, palette Palette) string {
	chars := patternChars[patternType]
	if len(chars) == 0 {
		chars = []string{"░", "▒", "▓", "█"}
	}

	var result strings.Builder
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			// Use position to deterministically select character
			idx := (x + y) % len(chars)
			result.WriteString(chars[idx])
		}
		result.WriteString("\n")
	}
	return result.String()
}

// getSidebarBackground returns styled background for sidebar
func getSidebarBackground(patternType string, palette Palette) string {
	switch patternType {
	case "hieroglyph":
		return palette.BgDark
	case "shadow":
		return "#080808"
	case "matrix":
		return "#001100"
	case "radar":
		return palette.BgDark
	case "bamboo":
		return "#0A0A0A"
	case "waves":
		return palette.BgDark
	case "gears":
		return "#151010"
	case "stars":
		return "#050510"
	default:
		return palette.BgDark
	}
}

// getChatBackground returns styled background for chat (different from sidebar)
func getChatBackground(patternType string, palette Palette) string {
	switch patternType {
	case "hieroglyph":
		return palette.BgMid
	case "shadow":
		return palette.BgMid
	case "matrix":
		return "#000800"
	case "radar":
		return "#0A1528"
	case "bamboo":
		return palette.BgMid
	case "waves":
		return "#000815"
	case "gears":
		return palette.BgMid
	case "stars":
		return palette.BgMid
	default:
		return palette.BgMid
	}
}

// ═══════════════════════════════════════════════════════════════════════════════
// BRAIN MAP - 5 nodes with single-word names
// ═══════════════════════════════════════════════════════════════════════════════

type BrainNode struct {
	Name        string // Single word name
	Description string
	Icon        string
	Color       string
	X, Y        int // Position in grid
}

// BrainMap nodes with themed icons
var brainNodes = []BrainNode{
	{Name: "Core", Description: "Central processing and routing", Icon: "🧠", Color: "#FF6B6B", X: 1, Y: 0},
	{Name: "Nexus", Description: "Cross-platform integration", Icon: "⚡", Color: "#58A6FF", X: 0, Y: 1},
	{Name: "Cortex", Description: "Pattern recognition and learning", Icon: "🔮", Color: "#A371F7", X: 2, Y: 1},
	{Name: "Memory", Description: "Storage and retrieval systems", Icon: "💾", Color: "#3FB950", X: 1, Y: 2},
	{Name: "Signal", Description: "Input/output and communication", Icon: "📡", Color: "#F778BA", X: 1, Y: 1},
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODEL STATE
// ═══════════════════════════════════════════════════════════════════════════════

type model struct {
	// Window dimensions
	width  int
	height int

	// Tab state (0=OpenCode, 1=OpenClaw)
	tab int

	// Data stores
	messages map[string][]Message
	input    string
	scrollY  map[string]int
	loading  bool

	// Memory system
	memoryPath    string
	memoryData    []MemoryEntry
	userProfile   UserProfile
	memCategories []MemoryCategory

	// Platform status
	platforms []PlatformStatus

	// Workers
	workers []Worker

	// UI States
	showConfig  bool
	showTheme   bool
	showBrain   bool
	startTime   time.Time
	configFocus int
	themeIndex  int
	config      Config

	// Platform navigation
	brainSelected int // Currently selected brain node (0-4)

	// Auto learning system
	autoLearning AutoLearning

	// Animation state (60 FPS)
	frameStep       int
	animationStep   float64
	pulseMath       float64
	diagnosticPulse float64
	timeAccumulator time.Duration

	// Diagnostics
	diagnostics DiagnosticData

	// Bubble Layout for declarative 3-pane layout
	layout *bubblelayout.BubbleLayout

	// Viewport for chat scrolling (pager style)
	chatViewport viewport.Model
	ready        bool
}

// ═══════════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════════

func initialModel() model {
	memPath := os.ExpandEnv("$HOME/.config/cortexllm/memory")

	return model{
		tab:     0,
		width:   0,
		height:  0,
		loading: false,
		messages: map[string][]Message{
			"opencode": {},
			"openclaw": {},
		},
		scrollY: map[string]int{
			"opencode": 0,
			"openclaw": 0,
		},
		memoryPath: memPath,
		memoryData: loadMemoryData(memPath),
		userProfile: UserProfile{
			Name:               "User",
			PreferredModel:     "qwen3.5:cloud",
			CommonTopics:       []string{"programming", "system design", "Go", "Python"},
			CommunicationStyle: "concise",
			KnownFacts: map[string]string{
				"github":   "github.com/user",
				"location": "Linux desktop",
				"editor":   "VSCode",
			},
		},
		platforms: []PlatformStatus{
			{Name: "opencode", Online: true, LastPing: time.Now(), Latency: 45, Model: "qwen3.5:cloud"},
			{Name: "openclaw", Online: false, LastPing: time.Now(), Latency: 0, Model: "qwen3.5:cloud"},
		},
		config: Config{
			OllamaKey:     "",
			Brain:         "qwen3.5:cloud",
			Hand:          "qwen2.5:7b",
			OpenCodeModel: "kimi",
			OpenClawModel: "qwen3.5:cloud",
			Platforms: map[string]PlatformConfig{
				"openclaw": {Enabled: true, Mode: "cli", TokenEnv: "OPENCLAW_GATEWAY_TOKEN", SessionPrefix: "cortexllm-"},
				"opencode": {Enabled: true, Mode: "ollama", Endpoint: "http://127.0.0.1:11434"},
			},
		},
		workers: []Worker{},
		autoLearning: AutoLearning{
			Keywords:    []string{"Go", "AI", "memory", "system design"},
			TaskTypes:   []string{"Coding", "Debugging", "Design", "Documentation"},
			Patterns:    []string{"Error handling", "Concurrency", "API design"},
			Topics:      map[string]int{"Go": 45, "AI": 32, "Docker": 18, "Testing": 12},
			LastUpdated: time.Now(),
		},
		memCategories: []MemoryCategory{
			{
				Name:        "Topics Discussed",
				Items:       []string{"Go programming", "AI integration", "System design", "Memory management"},
				Color:       "#58A6FF",
				Icon:        "🧠",
				Description: "Keywords extracted from chats",
				Type:        "topics",
			},
			{
				Name:        "Code Patterns",
				Items:       []string{"Error handling", "Concurrent goroutines", "API design", "Testing strategies"},
				Color:       "#A371F7",
				Icon:        "⚡",
				Description: "Patterns identified in code",
				Type:        "patterns",
			},
			{
				Name:        "Task Analysis",
				Items:       []string{"Bug fixing (40%)", "Feature dev (35%)", "Refactoring (20%)", "Documentation (5%)"},
				Color:       "#F778BA",
				Icon:        "📊",
				Description: "Task types and distribution",
				Type:        "tasks",
			},
			{
				Name:        "Knowledge Base",
				Items:       []string{"Docker workflows", "Git commands", "Go modules", "Terminal shortcuts"},
				Color:       "#3FB950",
				Icon:        "💡",
				Description: "Extracted knowledge",
				Type:        "knowledge",
			},
		},
		showConfig:    false,
		showTheme:     false,
		showBrain:     false,
		startTime:     time.Now(),
		configFocus:   0,
		themeIndex:    0,
		brainSelected: 2, // Start with Cortex selected (index 2)
		frameStep:       0,
		animationStep:   0.0,
		pulseMath:       0.0,
		diagnosticPulse: 0.0,
		diagnostics: DiagnosticData{
			LatencyHistory: make([]int, 30),
			TokenHistory:   make([]int, 30),
			MaxPoints:      30,
		},
	}
}

func loadMemoryData(memPath string) []MemoryEntry {
	var entries []MemoryEntry

	// Load from CortexLLM hot memory files
	for _, platform := range []string{"opencode", "openclaw"} {
		hotFile := filepath.Join(memPath, "hot", platform+".json")
		if data, err := os.ReadFile(hotFile); err == nil {
			var msgs []MemoryEntry
			if err := json.Unmarshal(data, &msgs); err == nil {
				for i := range msgs {
					msgs[i].Platform = platform
				}
				entries = append(entries, msgs...)
			}
		}
	}

	// Also load from OpenClaw SQLite for session continuity
	dbPath := filepath.Join(os.Getenv("HOME"), ".openclaw", "state", "openclaw.sqlite")
	if _, err := os.Stat(dbPath); err == nil {
		// Query recent events from acp_replay_events
		cmd := exec.Command("sqlite3", "-json", dbPath,
			"SELECT session_key, update_json, at FROM acp_replay_events ORDER BY at DESC LIMIT 50")
		output, err := cmd.Output()
		if err == nil {
			var events []struct {
				SessionKey string `json:"session_key"`
				UpdateJSON string `json:"update_json"`
				At         int64  `json:"at"`
			}
			if err := json.Unmarshal(output, &events); err == nil {
				for _, ev := range events {
					var turnData struct {
						Turn struct {
							Role    string `json:"role"`
							Content string `json:"content"`
						} `json:"turn"`
					}
					if err := json.Unmarshal([]byte(ev.UpdateJSON), &turnData); err == nil {
						entries = append(entries, MemoryEntry{
							Timestamp: time.Unix(ev.At, 0),
							Role:      turnData.Turn.Role,
							Content:   turnData.Turn.Content,
							Platform:  strings.TrimPrefix(ev.SessionKey, "cortexllm-"),
						})
					}
				}
			}
		}
	}

	return entries
}

// saveMessages persists messages to disk with atomic write
func saveMessages(memPath string, platform string, messages []Message) error {
	hotDir := filepath.Join(memPath, "hot")
	if err := os.MkdirAll(hotDir, 0755); err != nil {
		return fmt.Errorf("failed to create hot dir: %w", err)
	}

	// Convert Message to MemoryEntry for storage
	entries := make([]MemoryEntry, len(messages))
	for i, msg := range messages {
		entries[i] = MemoryEntry{
			Timestamp: msg.Time,
			Role: func() string {
				if msg.IsUser {
					return "user"
				}
				return "assistant"
			}(),
			Content:   msg.Content,
			TokensIn:  msg.TokensIn,
			TokensOut: msg.TokensOut,
			Platform:  platform,
		}
	}

	data, err := json.MarshalIndent(entries, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal: %w", err)
	}

	// Atomic write: write to temp file, then rename
	hotFile := filepath.Join(hotDir, platform+".json")
	tmpFile := hotFile + ".tmp"

	if err := os.WriteFile(tmpFile, data, 0644); err != nil {
		return fmt.Errorf("failed to write temp file: %w", err)
	}

	if err := os.Rename(tmpFile, hotFile); err != nil {
		os.Remove(tmpFile) // Clean up temp file on failure
		return fmt.Errorf("failed to rename: %w", err)
	}

	return nil
}

// saveAllPlatforms saves messages for all platforms
func saveAllPlatforms(memPath string, messages map[string][]Message) {
	for platform, msgs := range messages {
		if err := saveMessages(memPath, platform, msgs); err != nil {
			fmt.Fprintf(os.Stderr, "Save error for %s: %v\n", platform, err)
		}
	}
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMMANDS
// ═══════════════════════════════════════════════════════════════════════════════

func (m model) Init() tea.Cmd {
	return tea.Batch(
		tick(),
		checkAllPlatforms(),
	)
}

type tickMsg struct{}
type openClawStatusMsg struct {
	online  bool
	latency int
}
type ollamaStatusMsg struct {
	online  bool
	latency int
}
type platformStatusMsg struct {
	platform string
	online   bool
	latency  int
}

func tick() tea.Cmd {
	return tea.Every(16*time.Millisecond, func(t time.Time) tea.Msg {
		return tickMsg{}
	})
}

func checkOpenClaw() tea.Cmd {
	return func() tea.Msg {
		// Check if OpenClaw is running on port 18789
		start := time.Now()
		cmd := exec.Command("curl", "-s", "-m", "2", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:18789/health")
		output, err := cmd.Output()
		latency := int(time.Since(start).Milliseconds())
		if err != nil {
			return platformStatusMsg{platform: "openclaw", online: false, latency: 0}
		}
		statusCode := strings.TrimSpace(string(output))
		return platformStatusMsg{platform: "openclaw", online: statusCode == "200", latency: latency}
	}
}

func checkOllama() tea.Cmd {
	return func() tea.Msg {
		// Check if Ollama is running on port 11434
		start := time.Now()
		cmd := exec.Command("curl", "-s", "-m", "2", "http://127.0.0.1:11434/api/tags")
		_, err := cmd.Output()
		latency := int(time.Since(start).Milliseconds())
		if err != nil {
			return platformStatusMsg{platform: "opencode", online: false, latency: 0}
		}
		return platformStatusMsg{platform: "opencode", online: true, latency: latency}
	}
}

func checkAllPlatforms() tea.Cmd {
	return tea.Batch(checkOpenClaw(), checkOllama())
}

func injectToOpenClaw(message string, platform string) tea.Cmd {
	return func() tea.Msg {
		// Use OpenClaw CLI with token from environment
		agentID := "brain"
		sessionKey := fmt.Sprintf("cortexllm-%s", platform)

		cmd := exec.Command("openclaw", "agent",
			"--agent", agentID,
			"--session-key", sessionKey,
			"--message", message,
			"--json")

		// Set token from environment variable
		token := os.Getenv("OPENCLAW_GATEWAY_TOKEN")
		if token == "" {
			return Message{Content: "OpenClaw: OPENCLAW_GATEWAY_TOKEN not set", IsUser: false, Platform: platform, Time: time.Now()}
		}
		cmd.Env = append(os.Environ(), "OPENCLAW_GATEWAY_TOKEN="+token)

		output, err := cmd.CombinedOutput()
		if err != nil {
			return Message{Content: fmt.Sprintf("OpenClaw: %v", err), IsUser: false, Platform: platform, Time: time.Now()}
		}

		// Parse JSON response - OpenClaw returns {result:{payloads:[{text:...}]}}
		var response struct {
			Result struct {
				Payloads []struct {
					Text string `json:"text"`
				} `json:"payloads"`
			} `json:"result"`
		}
		if err := json.Unmarshal(output, &response); err != nil {
			return Message{Content: string(output), IsUser: false, Platform: platform, Time: time.Now()}
		}

		reply := ""
		if len(response.Result.Payloads) > 0 {
			reply = response.Result.Payloads[0].Text
		}

		// Save response to memory
		saveMessages(os.ExpandEnv("$HOME/.config/cortexllm/memory"), platform, []Message{
			{Content: message, IsUser: true, Platform: platform, Time: time.Now()},
			{Content: reply, IsUser: false, Platform: platform, Time: time.Now()},
		})

		return Message{Content: reply, IsUser: false, Platform: platform, Time: time.Now()}
	}
}

func sendToOpenCode(message string) tea.Cmd {
	return injectToOpenClaw(message, "opencode")
}

func sendToOpenClaw(message string) tea.Cmd {
	return injectToOpenClaw(message, "openclaw")
}

// sendToOllamaDirect sends a message directly to Ollama API (fallback mode)
func sendToOllamaDirect(message string, model string) tea.Cmd {
	return func() tea.Msg {
		endpoint := os.Getenv("OLLAMA_HOST")
		if endpoint == "" {
			endpoint = "http://127.0.0.1:11434"
		}

		payload := map[string]interface{}{
			"model":  model,
			"prompt": message,
			"stream": false,
		}

		payloadJSON, err := json.Marshal(payload)
		if err != nil {
			return Message{Content: fmt.Sprintf("Ollama: failed to marshal payload: %v", err), IsUser: false, Platform: "ollama", Time: time.Now()}
		}

		cmd := exec.Command("curl", "-s", "-X", "POST",
			endpoint+"/api/generate",
			"-H", "Content-Type: application/json",
			"-d", string(payloadJSON))

		output, err := cmd.Output()
		if err != nil {
			return Message{Content: fmt.Sprintf("Ollama: %v", err), IsUser: false, Platform: "ollama", Time: time.Now()}
		}

		var response struct {
			Response string `json:"response"`
		}
		if err := json.Unmarshal(output, &response); err != nil {
			return Message{Content: string(output), IsUser: false, Platform: "ollama", Time: time.Now()}
		}

		return Message{Content: response.Response, IsUser: false, Platform: "ollama", Time: time.Now()}
	}
}

// ═══════════════════════════════════════════════════════════════════════════════
// UPDATE
// ═══════════════════════════════════════════════════════════════════════════════

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

		// Initialize viewport for chat if not ready
		if !m.ready {
			// Chat area is 60% of width, minus padding (2+2=4), minus border allowance (2)
			chatWidth := int(float64(msg.Width)*0.60) - 8
			chatHeight := msg.Height - 5 // Leave room for input
			if chatWidth > 0 && chatHeight > 0 {
				m.chatViewport = viewport.New(chatWidth, chatHeight)
				m.chatViewport.SetContent(m.buildChatContent())
				m.ready = true
			}
		} else {
			// Update viewport size - same calculation as initialization
			chatWidth := int(float64(msg.Width)*0.60) - 8
			chatHeight := msg.Height - 5
			if chatWidth > 0 && chatHeight > 0 {
				m.chatViewport.Width = chatWidth
				m.chatViewport.Height = chatHeight
			}
		}
		return m, nil

	case tickMsg:
		// 60 FPS Animation Loop
		m.frameStep = (m.frameStep + 1) % 60
		m.animationStep += 0.08
		if m.animationStep >= 1.0 {
			m.animationStep = 0.0
		}
		m.pulseMath += 0.1
		m.diagnosticPulse += 0.05

		// Check platform status every 120 frames (2 seconds at 60fps)
		// Auto-save messages every 120 frames (2 seconds)
		var platformCmd tea.Cmd
		if m.frameStep == 0 {
			platformCmd = checkAllPlatforms()
			// Auto-save all platforms
			saveAllPlatforms(m.memoryPath, m.messages)
		}

		return m, tea.Batch(tick(), platformCmd)

	case platformStatusMsg:
		// Update platform status
		for i := range m.platforms {
			if m.platforms[i].Name == msg.platform {
				m.platforms[i].Online = msg.online
				m.platforms[i].Latency = msg.latency
				m.platforms[i].LastPing = time.Now()
			}
		}
		return m, nil

	case Message:
		// Received message from platform
		m.messages[msg.Platform] = append(m.messages[msg.Platform], msg)
		// Save immediately after receiving AI response
		saveMessages(m.memoryPath, msg.Platform, m.messages[msg.Platform])
		// Update viewport content if on chat tab
		if m.tab < 2 && m.ready {
			m.chatViewport.SetContent(m.buildChatContent())
			// Auto-scroll to bottom
			m.chatViewport.GotoBottom()
		}
		return m, nil

	case tea.KeyMsg:
		// Handle config overlay mode
		if m.showConfig {
			return m.updateConfig(msg)
		}

		// Handle theme picker mode
		if m.showTheme {
			return m.updateTheme(msg)
		}

		switch msg.Type {
		case tea.KeyEsc:
			// Save all messages before quitting
			saveAllPlatforms(m.memoryPath, m.messages)
			return m, tea.Quit

		case tea.KeyCtrlP:
			m.showConfig = true
			m.configFocus = 0
			return m, nil

		case tea.KeyCtrlC:
			// Save all messages before quitting
			saveAllPlatforms(m.memoryPath, m.messages)
			return m, tea.Quit

		case tea.KeyCtrlT:
			m.showTheme = true
			return m, nil

		case tea.KeyTab:
			m.tab = (m.tab + 1) % 2
			m.loading = false
			return m, nil

		case tea.KeyUp:
			// Scroll viewport up
			if m.tab < 2 && m.ready {
				m.chatViewport.LineUp(1)
			}
			return m, nil

		case tea.KeyDown:
			// Scroll viewport down
			if m.tab < 2 && m.ready {
				m.chatViewport.LineDown(1)
			}
			return m, nil

		case tea.KeyEnter:
			if m.input != "" && m.tab < 2 {
				platform := currentPlatform(m.tab)
				text := m.input
				m.input = ""

				// Add user message
				m.messages[platform] = append(m.messages[platform], Message{
					Platform: platform,
					Content:  text,
					IsUser:   true,
					Time:     time.Now(),
				})

				// Save user message immediately
				saveMessages(m.memoryPath, platform, m.messages[platform])

				// Reset scroll
				m.scrollY[platform] = 0

				// Inject message to platform inbox (no direct model calls)
				switch platform {
				case "opencode":
					return m, sendToOpenCode(text)
				case "openclaw":
					return m, sendToOpenClaw(text)
				}
			}
			return m, nil

		case tea.KeyBackspace:
			if len(m.input) > 0 {
				m.input = m.input[:len(m.input)-1]
			}
			return m, nil

		case tea.KeySpace:
			m.input += " "
			return m, nil

		case tea.KeyRunes:
			m.input += string(msg.Runes)
			return m, nil
		}
	}
	return m, nil
}

func (m model) updateConfig(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.Type {
	case tea.KeyEsc:
		m.showConfig = false
		return m, nil
	case tea.KeyTab:
		m.configFocus = (m.configFocus + 1) % 2
		return m, nil
	case tea.KeyUp:
		if m.configFocus > 0 {
			m.configFocus--
		}
		return m, nil
	case tea.KeyDown:
		if m.configFocus < 1 {
			m.configFocus++
		}
		return m, nil
	case tea.KeyEnter:
		// Select current model from dropdown
		if m.configFocus == 0 {
			// Brain model - cycle through available
			currentIdx := -1
			for i, model := range availableModels {
				if model.Name == m.config.Brain {
					currentIdx = i
					break
				}
			}
			if currentIdx >= 0 {
				nextIdx := (currentIdx + 1) % len(availableModels)
				m.config.Brain = availableModels[nextIdx].Name
			} else {
				m.config.Brain = availableModels[0].Name
			}
		} else if m.configFocus == 1 {
			// Worker model - cycle through available
			currentIdx := -1
			for i, model := range availableModels {
				if model.Name == m.config.Hand {
					currentIdx = i
					break
				}
			}
			if currentIdx >= 0 {
				nextIdx := (currentIdx + 1) % len(availableModels)
				m.config.Hand = availableModels[nextIdx].Name
			} else {
				m.config.Hand = availableModels[0].Name
			}
		}
		return m, nil
	}
	return m, nil
}

func (m model) updateTheme(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.Type {
	case tea.KeyEsc:
		m.showTheme = false
		return m, nil
	case tea.KeyTab, tea.KeyDown:
		m.themeIndex = (m.themeIndex + 1) % len(themes)
		return m, nil
	case tea.KeyUp:
		m.themeIndex--
		if m.themeIndex < 0 {
			m.themeIndex = len(themes) - 1
		}
		return m, nil
	case tea.KeyEnter:
		m.showTheme = false
		return m, nil
	}
	return m, nil
}

func currentPlatform(tab int) string {
	switch tab {
	case 0:
		return "opencode"
	case 1:
		return "openclaw"
	}
	return "opencode"
}

// ═══════════════════════════════════════════════════════════════════════════════
// VIEW
// ═══════════════════════════════════════════════════════════════════════════════

func (m model) View() string {
	if m.width == 0 || m.height == 0 {
		return "Loading..."
	}

	// Handle overlays
	if m.showConfig {
		return m.renderConfigOverlay()
	}
	if m.showTheme {
		return m.renderThemePicker()
	}

	// Main 2-pane layout: Diagnostics (left) | Chat (right)
	content := m.renderMainContent()
	diagnostics := m.renderDiagnosticsPanel()

	return lipgloss.JoinHorizontal(lipgloss.Top, diagnostics, content)
}

// ═══════════════════════════════════════════════════════════════════════════════
// SIDEBAR (20% width)
// ═══════════════════════════════════════════════════════════════════════════════

func (m model) renderSidebar() string {
	width := int(float64(m.width) * 0.20)
	if width < 20 {
		width = 20
	}
	if width > 35 {
		width = 35
	}

	var content strings.Builder
	// Use current RPG theme palette for richer colors
	rpgTheme := rpgThemes[m.themeIndex]
	palette := rpgTheme.Palette

	// Header with static icon (no animation to prevent jumping)
	headerIcon := rpgTheme.Icon
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.Primary)).
		Bold(true).
		Render(fmt.Sprintf("%s CORTEX", headerIcon)))
	content.WriteString("\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("Unified AI Console"))
	content.WriteString("\n\n")

	// User section with static avatar (no animation to prevent jumping)
	userAvatar := rpgTheme.Icon
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("USER"))
	content.WriteString("\n")
	userLine := lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.Primary)).
		Bold(true).
		Render(fmt.Sprintf("  %s User", userAvatar))
	content.WriteString(userLine)
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render(fmt.Sprintf("  // %s", rpgTheme.Name)))
	content.WriteString("\n\n")

	// Platforms section with themed icons
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("PLATFORMS"))
	content.WriteString("\n")

	for i, p := range m.platforms {
		// Use PlatformSet avatars from theme

		// Status indicator with theme colors
		var statusSymbol string
		var statusColor string
		if p.Online {
			pulse := math.Abs(math.Sin(m.diagnosticPulse + float64(i)))
			if pulse > 0.7 {
				statusSymbol = rpgTheme.StatusOn
			} else {
				statusSymbol = rpgTheme.StatusOff
			}
			statusColor = palette.Success
		} else {
			statusSymbol = rpgTheme.StatusOff
			statusColor = palette.Error
		}

		// Selection indicator with high contrast
		selected := m.tab == i
		var tabBox string
		var nameStyle lipgloss.Style
		
		if selected {
			// Selected: bright background, dark text, bold
			nameStyle = lipgloss.NewStyle().
				Background(lipgloss.Color(palette.Primary)).
				Foreground(lipgloss.Color("#0F172A")).
				Bold(true).
				Padding(0, 2)
			tabBox = fmt.Sprintf("▌ %s ▐", strings.ToUpper(strings.Title(p.Name)))
		} else {
			// Unselected: dim text, no background
			nameStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color(palette.TextDim)).
				Padding(0, 2)
			tabBox = fmt.Sprintf("  %s  ", strings.Title(p.Name))
		}

		line := fmt.Sprintf("%s %s",
			lipgloss.NewStyle().Foreground(lipgloss.Color(statusColor)).Render(statusSymbol),
			nameStyle.Render(tabBox))

		content.WriteString(line)
		content.WriteString("\n")
	}

	content.WriteString("\n")

	// Platform tabs render
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("SYSTEM"))
	content.WriteString("\n")

	memStyle := lipgloss.NewStyle()
	if m.tab == 2 {
		memStyle = memStyle.
			Background(lipgloss.Color(palette.Primary)).
			Foreground(lipgloss.Color(palette.BgDark)).
			Bold(true)
	} else {
		memStyle = memStyle.Foreground(lipgloss.Color(palette.Text))
	}

	memName := "Memory"
	if m.tab == 2 {
		memName = "> Memory"
	} else {
		memName = "  Memory"
	}

	content.WriteString(fmt.Sprintf("  %s %s", brainNodes[3].Icon, memStyle.Render(memName)))

	// Fill to bottom
	content.WriteString("\n\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("CortexLLM"))
	content.WriteString("\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("github.com/greyok00/cortexllm"))

	sidebarBg := getSidebarBackground(rpgTheme.Pattern, palette)

	return lipgloss.NewStyle().
		Width(width).
		Height(m.height).
		Background(lipgloss.Color(sidebarBg)).
		Padding(1, 1).
		Render(content.String())
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN CONTENT (60% width)
// ═══════════════════════════════════════════════════════════════════════════════

func (m model) renderMainContent() string {
	width := int(float64(m.width) * 0.60)
	_ = themes[m.themeIndex] // theme is used in sub-renders

	if m.tab == 2 {
		return m.renderMemoryMatrix(width)
	}

	return m.renderChat(width)
}

func (m model) buildChatContent() string {
	platform := currentPlatform(m.tab)
	rpgTheme := rpgThemes[m.themeIndex]
	palette := rpgTheme.Palette
	msgs := m.messages[platform]

	// Calculate usable width for messages
	// Chat area is 60% of screen width, minus viewport padding/borders (8 total)
	// The wrapText function works on plain text, so we need extra margin for safety
	chatWidth := int(float64(m.width)*0.60) - 14
	if chatWidth < 20 {
		chatWidth = 20 // Minimum width
	}

	// Platform-specific colors for AI messages
	platformColors := map[string]string{
		"opencode": "#FFFFFF", // White
		"openclaw": "#FF4444", // Red
	}
	aiColor := platformColors[platform]

	var content strings.Builder

	for _, msg := range msgs {
		timeStr := msg.Time.Format("3:04 PM")

		// Word wrap the message content
		wrappedContent := wrapText(msg.Content, chatWidth-2)

		if msg.IsUser {
			// USER MESSAGE - Large RPG class avatar on left, color-coded
			userAvatar := rpgTheme.Icon // Use the main RPG class icon

			// Avatar with border
			avatarStyle := lipgloss.NewStyle().
				Foreground(lipgloss.Color(palette.Primary)).
				Background(lipgloss.Color(palette.BgDark)).
				Padding(0, 1).
				Bold(true)

			// Username and timestamp
			nameStyle := lipgloss.NewStyle().
				Foreground(lipgloss.Color(palette.Primary)).
				Bold(true)

			timeStyle := lipgloss.NewStyle().
				Foreground(lipgloss.Color(palette.TextDim))

			// Build user message
			content.WriteString(avatarStyle.Render(userAvatar))
			content.WriteString(" ")
			content.WriteString(nameStyle.Render("User"))
			content.WriteString(" ")
			content.WriteString(timeStyle.Render(timeStr))
			content.WriteString("\n")
			content.WriteString(wrappedContent)
			content.WriteString("\n\n")

		} else {
			// AI MESSAGE - Large avatar on left, platform color
			// Get platform-specific large avatar
			var aiAvatar string
			switch platform {
			case "opencode":
				aiAvatar = "◉" // Large white circle
			case "openclaw":
				aiAvatar = "🦞" // Lobster
			default:
				aiAvatar = "🤖"
			}

			// Avatar with platform color border
			avatarStyle := lipgloss.NewStyle().
				Foreground(lipgloss.Color(aiColor)).
				Background(lipgloss.Color(palette.BgDark)).
				Padding(0, 1).
				Bold(true)

			// AI name with platform color
			nameStyle := lipgloss.NewStyle().
				Foreground(lipgloss.Color(aiColor)).
				Bold(true)

			timeStyle := lipgloss.NewStyle().
				Foreground(lipgloss.Color(palette.TextDim))

			// Build AI message
			content.WriteString(avatarStyle.Render(aiAvatar))
			content.WriteString(" ")
			content.WriteString(nameStyle.Render(strings.Title(platform)))
			content.WriteString(" ")
			content.WriteString(timeStyle.Render(timeStr))
			content.WriteString("\n")
			content.WriteString(wrappedContent)
			content.WriteString("\n\n")
		}
	}

	return content.String()
}

// wrapText wraps text at the specified width
func wrapText(text string, width int) string {
	if width <= 0 {
		return text
	}

	var result strings.Builder
	words := strings.Fields(text)
	currentLine := ""

	for _, word := range words {
		if len(currentLine)+len(word)+1 > width {
			result.WriteString(currentLine)
			result.WriteString("\n")
			currentLine = word
		} else {
			if currentLine != "" {
				currentLine += " "
			}
			currentLine += word
		}
	}

	if currentLine != "" {
		result.WriteString(currentLine)
	}

	return result.String()
}

func (m model) renderChat(width int) string {
	rpgTheme := rpgThemes[m.themeIndex]
	palette := rpgTheme.Palette

	// Update viewport content
	m.chatViewport.SetContent(m.buildChatContent())

	var content strings.Builder

	// Use the viewport for chat content
	content.WriteString(m.chatViewport.View())

	// Input Bar at bottom
	content.WriteString("\n")
	inputStyle := lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.Primary)).
		Bold(true)

	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.BgLight)).
		Render(strings.Repeat("─", width-4)))
	content.WriteString("\n")
	content.WriteString(inputStyle.Render("❯ "))
	content.WriteString(m.input)
	content.WriteString("▋")

	chatBg := getChatBackground(rpgTheme.Pattern, palette)

	return lipgloss.NewStyle().
		Width(width).
		Height(m.height).
		Background(lipgloss.Color(chatBg)).
		Border(lipgloss.NormalBorder(), false, true, false, false).
		BorderForeground(lipgloss.Color(palette.BgLight)).
		Padding(1, 2).
		Render(content.String())
}

func (m model) renderMemoryMatrix(width int) string {
	// Use RPG theme palette
	rpgTheme := rpgThemes[m.themeIndex]
	palette := rpgTheme.Palette

	var content strings.Builder

	// Header with static icon (no animation to prevent jumping)
	memoryIcon := rpgTheme.Icon

	// Simple header without complex parsing
	headerStyle := lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.Primary)).
		Bold(true)
	content.WriteString(headerStyle.Render(fmt.Sprintf("%s  MEMORY MATRIX", memoryIcon)))
	content.WriteString("\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("What CortexLLM knows about you"))
	content.WriteString("\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.BgLight)).
		Render(strings.Repeat("─", width-4)))
	content.WriteString("\n\n")

	// 2x2 Grid of memory categories
	cardWidth := (width - 10) / 2

	for i := 0; i < len(m.memCategories); i += 2 {
		row := []string{}

		// Card 1
		card1 := m.renderMemoryCard(m.memCategories[i], cardWidth, palette)
		row = append(row, card1)

		// Card 2
		if i+1 < len(m.memCategories) {
			card2 := m.renderMemoryCard(m.memCategories[i+1], cardWidth, palette)
			row = append(row, card2)
		}

		content.WriteString(lipgloss.JoinHorizontal(lipgloss.Top, row...))
		content.WriteString("\n")
	}

	return lipgloss.NewStyle().
		Width(width).
		Height(m.height).
		Background(lipgloss.Color(palette.BgMid)).
		Border(lipgloss.NormalBorder(), false, true, false, false).
		BorderForeground(lipgloss.Color(palette.BgLight)).
		Padding(1, 2).
		Render(content.String())
}

func (m model) renderMemoryCard(cat MemoryCategory, width int, palette Palette) string {
	var content strings.Builder

	// Header
	header := lipgloss.NewStyle().
		Foreground(lipgloss.Color(cat.Color)).
		Bold(true).
		Render(fmt.Sprintf("%s %s", cat.Icon, cat.Name))
	content.WriteString(header)
	content.WriteString("\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render(cat.Description))
	content.WriteString("\n\n")

	// Items
	for _, item := range cat.Items {
		content.WriteString(lipgloss.NewStyle().
			Foreground(lipgloss.Color(palette.Text)).
			Render("  • " + item))
		content.WriteString("\n")
	}

	return lipgloss.NewStyle().
		Width(width).
		Height(12).
		Background(lipgloss.Color(palette.BgDark)).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color(cat.Color)).
		Padding(1).
		Render(content.String())
}

// ═══════════════════════════════════════════════════════════════════════════════
// DIAGNOSTICS PANEL (20% width) - Platform Status Only
// ═══════════════════════════════════════════════════════════════════════════════

func (m model) renderDiagnosticsPanel() string {
	width := int(float64(m.width) * 0.20)
	if width < 25 {
		width = 25
	}
	if width > 40 {
		width = 40
	}
	// Use RPG theme palette
	rpgTheme := rpgThemes[m.themeIndex]
	palette := rpgTheme.Palette

	var content strings.Builder

	// Header with static icon (no animation)
	diagIcon := "◆"
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.Primary)).
		Bold(true).
		Render(fmt.Sprintf("%s PLATFORMS", diagIcon)))
	content.WriteString("\n\n")

	// Platform Status with latency
	for _, p := range m.platforms {
		// Icon based on platform
		var platformIcon string
		switch p.Name {
		case "opencode":
			platformIcon = "◉" // White circle
		case "openclaw":
			platformIcon = "🦞" // Lobster
		default:
			platformIcon = "●"
		}

		// Status indicator
		var statusIcon string
		var statusColor string
		if p.Online {
			statusIcon = rpgTheme.StatusOn
			statusColor = palette.Success
		} else {
			statusIcon = rpgTheme.StatusOff
			statusColor = palette.Error
		}

		// Platform name with icon
		nameStyle := lipgloss.NewStyle().
			Foreground(lipgloss.Color(palette.Text)).
			Bold(m.tab < 2 && currentPlatform(m.tab) == p.Name)

		content.WriteString(lipgloss.NewStyle().
			Foreground(lipgloss.Color(statusColor)).
			Render(statusIcon))
		content.WriteString(" ")
		content.WriteString(lipgloss.NewStyle().
			Foreground(lipgloss.Color(palette.TextDim)).
			Render(platformIcon))
		content.WriteString(" ")
		content.WriteString(nameStyle.Render(strings.Title(p.Name)))

		// Online/offline indicator only (no inline latency - shown in System section)
		if !p.Online {
			content.WriteString(lipgloss.NewStyle().
				Foreground(lipgloss.Color(palette.TextDim)).
				Render(" offline"))
		}
		content.WriteString("\n")
	}

	content.WriteString("\n")

	// System Status
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("SYSTEM"))
	content.WriteString("\n")
	// Gateway latency
	content.WriteString(lipgloss.NewStyle().Foreground(lipgloss.Color(palette.Text)).Render(fmt.Sprintf("◆ Gateway: %dms", m.platforms[1].Latency)))
	content.WriteString("\n")
	// Ollama latency
	content.WriteString(lipgloss.NewStyle().Foreground(lipgloss.Color(palette.Text)).Render(fmt.Sprintf("◆ Ollama: %dms", m.platforms[0].Latency)))
	content.WriteString("\n")
	// Uptime
	uptime := int(time.Since(m.startTime).Seconds())
	content.WriteString(lipgloss.NewStyle().Foreground(lipgloss.Color(palette.Text)).Render(fmt.Sprintf("◆ Uptime: %ds", uptime)))
	content.WriteString("\n")

	// Fill remaining space properly
	currentLines := strings.Count(content.String(), "\n")
	for currentLines < m.height-5 {
		content.WriteString("\n")
		currentLines++
	}

	// Footer with controls
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("Tab: Switch │ Ctrl+T: Theme │ Ctrl+P: Config │ Ctrl+C: Quit"))

	diagBg := getSidebarBackground(rpgTheme.Pattern, palette)

	return lipgloss.NewStyle().
		Width(width).
		Height(m.height).
		Background(lipgloss.Color(diagBg)).
		Padding(1, 1).
		Render(content.String())
}

func (m model) renderSparkline(data []int, width int, palette Palette) string {
	if len(data) == 0 {
		return ""
	}

	// Find min/max
	min, max := data[0], data[0]
	for _, v := range data {
		if v < min {
			min = v
		}
		if v > max {
			max = v
		}
	}
	if max == min {
		max = min + 1
	}

	// Build sparkline
	var sparkline strings.Builder
	start := len(data) - width
	if start < 0 {
		start = 0
	}

	for i := start; i < len(data); i++ {
		v := data[i]
		idx := int((float64(v-min) / float64(max-min)) * float64(len(waveChars)-1))
		if idx >= len(waveChars) {
			idx = len(waveChars) - 1
		}
		if idx < 0 {
			idx = 0
		}
		sparkline.WriteString(waveChars[idx])
	}

	// Use palette highlight color
	return lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.Highlight)).
		Render(sparkline.String())
}

func (m model) renderBarChart(label string, value, max float64, width int, palette Palette) string {
	percent := value / max
	if percent > 1.0 {
		percent = 1.0
	}

	// Color interpolation using palette
	var barColor string
	if percent < 0.5 {
		barColor = palette.Success
	} else if percent < 0.8 {
		barColor = palette.Warning
	} else {
		barColor = palette.Error
	}

	// Build bar
	barWidth := width - 10
	filled := int(percent * float64(barWidth))

	var bar strings.Builder
	for i := 0; i < filled; i++ {
		bar.WriteString("█")
	}
	for i := filled; i < barWidth; i++ {
		bar.WriteString("░")
	}

	return lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.Text)).
		Render(fmt.Sprintf("%-4s[%s] %3.0f%%",
			label,
			lipgloss.NewStyle().Foreground(lipgloss.Color(barColor)).Render(bar.String()),
			percent*100))
}

// ═══════════════════════════════════════════════════════════════════════════════
// CONFIGURATION - Simplified with Model Dropdowns
// ═══════════════════════════════════════════════════════════════════════════════

// Available models for dropdown
type ModelOption struct {
	Name        string
	Description string
}

var availableModels = []ModelOption{
	{Name: "qwen3.5:cloud", Description: "Fast general purpose"},
	{Name: "qwen2.5-coder:14b", Description: "Code specialized"},
	{Name: "qwen2.5:7b", Description: "Balanced speed/quality"},
	{Name: "llama3.1:8b", Description: "Meta Llama 3"},
	{Name: "codellama:7b", Description: "Code generation"},
	{Name: "mistral:7b", Description: "Mistral general"},
	{Name: "mixtral:8x7b", Description: "Mixtral MoE"},
}

func (m model) renderConfigOverlay() string {
	width := m.width
	height := m.height
	panelWidth := 65
	if panelWidth > width-4 {
		panelWidth = width - 4
	}
	rpgTheme := rpgThemes[m.themeIndex]
	palette := rpgTheme.Palette

	var content strings.Builder

	// Title with brain icon
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.Primary)).
		Bold(true).
		Render("🧠 BRAIN CONFIGURATION"))
	content.WriteString("\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("Select AI models for processing"))
	content.WriteString("\n\n")

	// Brain Section
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("BRAIN"))
	content.WriteString("\n")

	// Current selection
	brainStyle := lipgloss.NewStyle().
		Background(lipgloss.Color(palette.BgDark)).
		Foreground(lipgloss.Color(palette.Primary)).
		Padding(0, 1).
		Width(panelWidth - 6)

	if m.configFocus == 0 {
		brainStyle = brainStyle.
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color(palette.Primary))
	}

	content.WriteString(brainStyle.Render("▶ " + m.config.Brain))
	content.WriteString("\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("Main reasoning and routing model"))
	content.WriteString("\n\n")

	// Show dropdown if focused
	if m.configFocus == 0 {
		content.WriteString(lipgloss.NewStyle().
			Foreground(lipgloss.Color(palette.TextDim)).
			Render("Available models:"))
		content.WriteString("\n")
		for _, model := range availableModels {
			marker := "  "
			if model.Name == m.config.Brain {
				marker = "▶ "
			}
			content.WriteString(lipgloss.NewStyle().
				Foreground(lipgloss.Color(palette.Text)).
				Render(marker + model.Name))
			content.WriteString(lipgloss.NewStyle().
				Foreground(lipgloss.Color(palette.TextDim)).
				Render(" - " + model.Description))
			content.WriteString("\n")
		}
		content.WriteString("\n")
	}

	// Hand Section
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("HAND"))
	content.WriteString("\n")

	workerStyle := lipgloss.NewStyle().
		Background(lipgloss.Color(palette.BgDark)).
		Foreground(lipgloss.Color(palette.Secondary)).
		Padding(0, 1).
		Width(panelWidth - 6)

	if m.configFocus == 1 {
		workerStyle = workerStyle.
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color(palette.Secondary))
	}

	content.WriteString(workerStyle.Render("▶ " + m.config.Hand))
	content.WriteString("\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("Task execution and completion"))
	content.WriteString("\n\n")

	// Show dropdown if focused
	if m.configFocus == 1 {
		content.WriteString(lipgloss.NewStyle().
			Foreground(lipgloss.Color(palette.TextDim)).
			Render("Available models:"))
		content.WriteString("\n")
		for _, model := range availableModels {
			marker := "  "
			if model.Name == m.config.Hand {
				marker = "▶ "
			}
			content.WriteString(lipgloss.NewStyle().
				Foreground(lipgloss.Color(palette.Text)).
				Render(marker + model.Name))
			content.WriteString(lipgloss.NewStyle().
				Foreground(lipgloss.Color(palette.TextDim)).
				Render(" - " + model.Description))
			content.WriteString("\n")
		}
		content.WriteString("\n")
	}

	// Workers Status Section
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("WORKER STATUS"))
	content.WriteString("\n")

	workers := []struct {
		name   string
		status string
		desc   string
	}{
		{"MemorySync", "running", "Auto-save every 2s"},
		{"PatternExtractor", "running", "Learning from chats"},
		{"HealthMonitor", "running", "Platform status"},
	}

	for _, w := range workers {
		statusColor := palette.Success
		if w.status == "idle" {
			statusColor = palette.TextDim
		}
		content.WriteString(lipgloss.NewStyle().
			Foreground(lipgloss.Color(statusColor)).
			Render("●"))
		content.WriteString(" ")
		content.WriteString(lipgloss.NewStyle().
			Foreground(lipgloss.Color(palette.Text)).
			Render(w.name))
		content.WriteString(lipgloss.NewStyle().
			Foreground(lipgloss.Color(palette.TextDim)).
			Render(fmt.Sprintf(" (%s)", w.desc)))
		content.WriteString("\n")
	}

	content.WriteString("\n")

	// Controls
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(palette.TextDim)).
		Render("↑↓: Navigate │ Enter: Select │ Esc: Close"))

	panel := lipgloss.NewStyle().
		Width(panelWidth).
		Background(lipgloss.Color(palette.BgDark)).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color(palette.Primary)).
		Padding(2).
		Render(content.String())

	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, panel)
}

func (m model) renderThemePicker() string {
	width := m.width
	height := m.height
	panelWidth := 55
	if panelWidth > width-4 {
		panelWidth = width - 4
	}
	// Limit height to fit on screen
	maxPanelHeight := height - 4
	if maxPanelHeight < 20 {
		maxPanelHeight = 20
	}

	currentTheme := rpgThemes[m.themeIndex]
	currentPalette := currentTheme.Palette

	var content strings.Builder

	// Title (no animation to prevent layout shifts)
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(currentPalette.Primary)).
		Bold(true).
		Render("⚔️ CHARACTER CLASS"))
	content.WriteString("\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(currentPalette.TextDim)).
		Render("Choose your RPG persona"))
	content.WriteString("\n\n")

	// Character class list - compact single-line view
	for i, rpg := range rpgThemes {
		isSelected := i == m.themeIndex

		if isSelected {
			// Selected theme - single line with preview
			marker := "▶ "

			// Compact class info
			classLine := lipgloss.NewStyle().
				Foreground(lipgloss.Color(rpg.Palette.Primary)).
				Bold(true).
				Render(fmt.Sprintf("%s %s", rpg.Icon, rpg.Name))

			classType := lipgloss.NewStyle().
				Foreground(lipgloss.Color(rpg.Palette.Secondary)).
				Render(fmt.Sprintf("(%s)", rpg.Name))

			// Mini palette (3 colors only)
			palettePreview := lipgloss.JoinHorizontal(lipgloss.Left,
				lipgloss.NewStyle().Background(lipgloss.Color(rpg.Palette.Primary)).Render(" "),
				lipgloss.NewStyle().Background(lipgloss.Color(rpg.Palette.Secondary)).Render(" "),
				lipgloss.NewStyle().Background(lipgloss.Color(rpg.Palette.Tertiary)).Render(" "),
			)

			content.WriteString(marker + classLine + " " + classType + " " + palettePreview)
			content.WriteString("\n")

			// Show description on separate compact line
			descStyle := lipgloss.NewStyle().
				Foreground(lipgloss.Color(rpg.Palette.TextDim)).
				Render(fmt.Sprintf("   %s", rpg.Description))
			content.WriteString(descStyle)
			content.WriteString("\n")
		} else {
			// Unselected - very compact
			marker := "  "
			classLine := lipgloss.NewStyle().
				Foreground(lipgloss.Color(rpg.Palette.TextDim)).
				Render(fmt.Sprintf("%s %s (%s)", rpg.Icon, rpg.Name, rpg.Name))

			content.WriteString(marker + classLine)
			content.WriteString("\n")
		}
	}

	// Controls at bottom
	content.WriteString("\n")
	content.WriteString(lipgloss.NewStyle().
		Foreground(lipgloss.Color(currentPalette.TextDim)).
		Render("↑↓: Navigate │ Enter: Select │ Esc: Cancel"))

	panel := lipgloss.NewStyle().
		Width(panelWidth).
		Background(lipgloss.Color(currentPalette.BgMid)).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color(currentPalette.Primary)).
		Padding(1, 2).
		Render(content.String())

	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, panel)
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════════════════════

const version = "2.0.0"

func main() {
	// Handle --version flag
	if len(os.Args) > 1 && (os.Args[1] == "--version" || os.Args[1] == "-v") {
		fmt.Printf("cortexllm version %s\n", version)
		os.Exit(0)
	}

	// Ensure memory directories exist
	memPath := os.ExpandEnv("$HOME/.config/cortexllm/memory")
	for _, dir := range []string{"hot", "warm", "cold"} {
		if err := os.MkdirAll(filepath.Join(memPath, dir), 0755); err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to create %s dir: %v\n", dir, err)
		}
	}

	p := tea.NewProgram(initialModel(), tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}
}
