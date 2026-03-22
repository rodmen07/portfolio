package middleware

import (
	"encoding/json"
	"net/http"
	"strings"
	"sync"

	"golang.org/x/time/rate"
)

// RateLimiter returns a middleware that enforces a per-route token bucket limit.
// The route key is the first two path segments (e.g. "/api/accounts").
func RateLimiter(rps float64) func(http.Handler) http.Handler {
	type entry struct {
		limiter *rate.Limiter
	}

	var mu sync.RWMutex
	limiters := make(map[string]*entry)

	getLimiter := func(key string) *rate.Limiter {
		mu.RLock()
		e, ok := limiters[key]
		mu.RUnlock()
		if ok {
			return e.limiter
		}

		mu.Lock()
		defer mu.Unlock()
		// double-check after acquiring write lock
		if e, ok = limiters[key]; ok {
			return e.limiter
		}
		l := rate.NewLimiter(rate.Limit(rps), int(rps)*2) // burst = 2× rps
		limiters[key] = &entry{limiter: l}
		return l
	}

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			key := routeKey(r.URL.Path)
			if !getLimiter(key).Allow() {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusTooManyRequests)
				_ = json.NewEncoder(w).Encode(map[string]string{
					"code":    "RATE_LIMITED",
					"message": "too many requests — slow down and retry",
				})
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

// routeKey extracts the first two path segments, e.g. "/api/accounts/foo" → "/api/accounts".
func routeKey(path string) string {
	parts := strings.SplitN(strings.TrimPrefix(path, "/"), "/", 3)
	if len(parts) >= 2 {
		return "/" + parts[0] + "/" + parts[1]
	}
	return path
}
