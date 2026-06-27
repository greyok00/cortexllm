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
	Enabled       bool   `json:"enabled"`
	Mode          string `json:"mode"`
	Endpoint      string `json:"endpoint,omitempty"`
	TokenEnv      string `json:"token_env,omitempty"`
	SessionPrefix string `json:"session_prefix,omitempty"`
}

type Config struct {
	OllamaKey string
	Brain     string // Primary reasoning model
	Hand      string // Task execution / worker model
	// Platform models
	OpenCodeModel string                    `json:"opencode_model"`
	OpenClawModel string                    `json:"openclaw_model"`
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
			PreferredModel:     "deepseek/deepseek-chat",
			CommonTopics:       []string{"programming", "system design", "Go", "Python"},
			CommunicationStyle: "concise",
			KnownFacts: map[string]string{
				"github":   "github.com/greyok00",
				"location": "Linux desktop",
				"editor":   "VSCode",
			},
		},
		platforms: []PlatformStatus{
			{Name: "opencode", Online: true, LastPing: time.Now(), Latency: 45, Model: "deepseek/deepseek-chat"},
			{Name: "openclaw", Online: false, LastPing: time.Now(), Latency: 0, Model: "deepseek/deepseek-chat"},
		},
		config: Config{
			OllamaKey:     "",
			Brain:         "qwen3.5:cloud",
			Hand:          "deepseek/deepseek-chat",
			OpenCodeModel: "kimi",
			OpenClawModel: "deepseek/deepseek-chat",
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
