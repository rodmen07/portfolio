package config

import (
	"os"
	"strconv"
)

// Config holds all runtime configuration for the gateway.
type Config struct {
	Port         string
	RateLimitRPS float64

	// Upstream service URLs
	TasksURL        string
	AccountsURL     string
	ContactsURL     string
	OpportunitiesURL string
	ActivitiesURL   string
	AutomationURL   string
	IntegrationsURL string
	ReportingURL    string
	SearchURL       string
	EventsURL       string
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// Load reads configuration from environment variables with production defaults.
func Load() Config {
	rps, err := strconv.ParseFloat(getenv("RATE_LIMIT_RPS", "10"), 64)
	if err != nil || rps <= 0 {
		rps = 10
	}

	return Config{
		Port:         getenv("PORT", "8091"),
		RateLimitRPS: rps,

		TasksURL:         getenv("TASKS_URL", "https://backend-service-rodmen07-v2.fly.dev"),
		AccountsURL:      getenv("ACCOUNTS_URL", "https://accounts-service.fly.dev"),
		ContactsURL:      getenv("CONTACTS_URL", "https://contacts-service.fly.dev"),
		OpportunitiesURL: getenv("OPPORTUNITIES_URL", "https://taskforge-opportunities-service.fly.dev"),
		ActivitiesURL:    getenv("ACTIVITIES_URL", "https://taskforge-activities-service.fly.dev"),
		AutomationURL:    getenv("AUTOMATION_URL", "https://taskforge-automation-service.fly.dev"),
		IntegrationsURL:  getenv("INTEGRATIONS_URL", "https://taskforge-integrations-service.fly.dev"),
		ReportingURL:     getenv("REPORTING_URL", "https://taskforge-reporting-service.fly.dev"),
		SearchURL:        getenv("SEARCH_URL", "https://taskforge-search-service.fly.dev"),
		EventsURL:        getenv("EVENTS_URL", "https://observaboard-rodmen07.fly.dev"),
	}
}
