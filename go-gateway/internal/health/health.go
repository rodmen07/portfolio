package health

import (
	"encoding/json"
	"net/http"
)

// Handler returns a simple health check response for the gateway itself.
func Handler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{
			"status":  "ok",
			"service": "go-gateway",
		})
	}
}
