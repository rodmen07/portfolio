package middleware

import (
	"fmt"
	"net/http"
	"time"
)

// statusRecorder wraps ResponseWriter to capture the status code after WriteHeader.
type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(code int) {
	r.status = code
	r.ResponseWriter.WriteHeader(code)
}

// Logger logs method, path, status, duration, and request ID for every request.
func Logger(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(rec, r)
		fmt.Printf(
			"method=%s path=%s status=%d duration_ms=%d request_id=%s\n",
			r.Method,
			r.URL.Path,
			rec.status,
			time.Since(start).Milliseconds(),
			r.Header.Get("X-Request-ID"),
		)
	})
}
