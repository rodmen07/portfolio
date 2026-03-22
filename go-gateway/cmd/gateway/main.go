package main

import (
	"fmt"
	"log"
	"net/http"

	"github.com/rodmen07/go-gateway/internal/config"
	"github.com/rodmen07/go-gateway/internal/health"
	"github.com/rodmen07/go-gateway/internal/middleware"
	"github.com/rodmen07/go-gateway/internal/proxy"
)

type route struct {
	prefix   string
	upstream string
}

func main() {
	cfg := config.Load()

	routes := []route{
		{"/api/tasks", cfg.TasksURL},
		{"/api/accounts", cfg.AccountsURL},
		{"/api/contacts", cfg.ContactsURL},
		{"/api/opportunities", cfg.OpportunitiesURL},
		{"/api/activities", cfg.ActivitiesURL},
		{"/api/automation", cfg.AutomationURL},
		{"/api/integrations", cfg.IntegrationsURL},
		{"/api/reporting", cfg.ReportingURL},
		{"/api/search", cfg.SearchURL},
		{"/api/events", cfg.EventsURL},
	}

	rateLimiter := middleware.RateLimiter(cfg.RateLimitRPS)

	mux := http.NewServeMux()

	// Gateway health — no rate limiting or logging needed
	mux.HandleFunc("/health", health.Handler())

	// Proxy routes — each wrapped with the full middleware chain
	for _, r := range routes {
		p := proxy.New(r.upstream, r.prefix)
		handler := middleware.Chain(p, middleware.Logger, middleware.RequestID, rateLimiter)
		mux.Handle(r.prefix+"/", handler)
		// Also match the prefix exactly (no trailing slash)
		mux.Handle(r.prefix, handler)
		fmt.Printf("  %-22s → %s\n", r.prefix+"/*", r.upstream)
	}

	addr := ":" + cfg.Port
	log.Printf("go-gateway listening on %s (rate limit: %.0f rps per route)\n", addr, cfg.RateLimitRPS)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatalf("server error: %v", err)
	}
}
