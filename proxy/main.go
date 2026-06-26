package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"sync"
	"time"
)

// MessageQueue holds messages to be injected
type MessageQueue struct {
	Messages []InjectionMessage `json:"messages"`
	mu       sync.Mutex
}

type InjectionMessage struct {
	Platform  string `json:"platform"`
	Content   string `json:"content"`
	Timestamp int64  `json:"timestamp"`
}

var messageQueue = &MessageQueue{Messages: []InjectionMessage{}}
var ollamaURL = "http://127.0.0.1:11434"

func main() {
	port := os.Getenv("CORTEX_PROXY_PORT")
	if port == "" {
		port = "11435" // Default proxy port
	}

	fmt.Printf("CortexLLM Proxy starting on port %s...\n", port)
	fmt.Printf("Forward to Ollama: %s\n", ollamaURL)

	// Create reverse proxy
	ollamaProxy := httputil.NewSingleHostReverseProxy(&url.URL{
		Scheme: "http",
		Host:   "127.0.0.1:11434",
	})

	// Wrap the proxy to intercept requests
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		// Log the request
		bodyBytes, _ := io.ReadAll(r.Body)
		r.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))

		var reqData map[string]interface{}
		if err := json.Unmarshal(bodyBytes, &reqData); err == nil {
			fmt.Printf("[MONITOR] %s %s - Model: %v\n",
				r.Method, r.URL.Path, reqData["model"])

			// Check for injections
			if msgs, ok := reqData["messages"].([]interface{}); ok {
				fmt.Printf("[MONITOR] Messages in request: %d\n", len(msgs))

				// Check if we have injections for this platform
				platform := detectPlatform(reqData)
				injected := checkForInjections(platform)
				if injected != "" {
					// Inject the message
					injectedMsg := map[string]string{
						"role":    "user",
						"content": injected,
					}
					reqData["messages"] = append(msgs, injectedMsg)

					// Rewrite body
					newBody, _ := json.Marshal(reqData)
					r.Body = io.NopCloser(bytes.NewBuffer(newBody))
					r.ContentLength = int64(len(newBody))

					fmt.Printf("[INJECT] Added message for %s: %s\n", platform, injected)
				}
			}
		} else {
			r.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))
		}

		// Forward to Ollama
		ollamaProxy.ServeHTTP(w, r)
	})

	// Injection API endpoint
	http.HandleFunc("/inject", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var injection InjectionMessage
		if err := json.NewDecoder(r.Body).Decode(&injection); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		injection.Timestamp = time.Now().Unix()

		messageQueue.mu.Lock()
		messageQueue.Messages = append(messageQueue.Messages, injection)
		messageQueue.mu.Unlock()

		fmt.Printf("[INJECT] Queued message for %s: %s\n", injection.Platform, injection.Content)

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "queued"})
	})

	// Status endpoint
	http.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":    "running",
			"port":      port,
			"ollama":    ollamaURL,
			"queue_len": len(messageQueue.Messages),
		})
	})

	fmt.Printf("\nTo use this proxy:\n")
	fmt.Printf("1. Set OLLAMA_HOST=http://127.0.0.1:%s for OpenCode/Claude/OpenClaw\n", port)
	fmt.Printf("2. Or configure each app to use 127.0.0.1:%s\n\n", port)

	http.ListenAndServe(":"+port, nil)
}

func detectPlatform(reqData map[string]interface{}) string {
	// Try to detect which app is calling based on model or other clues
	if model, ok := reqData["model"].(string); ok {
		switch model {
		case "kimi-k2.5:cloud", "kimi":
			return "opencode"
		case "claude", "claude-3-opus":
			return "claude"
		case "qwen3.5:cloud", "qwen":
			return "openclaw"
		}
	}
	return "unknown"
}

func checkForInjections(platform string) string {
	messageQueue.mu.Lock()
	defer messageQueue.mu.Unlock()

	for i, msg := range messageQueue.Messages {
		if msg.Platform == platform {
			// Remove from queue and return
			messageQueue.Messages = append(messageQueue.Messages[:i], messageQueue.Messages[i+1:]...)
			return msg.Content
		}
	}
	return ""
}
