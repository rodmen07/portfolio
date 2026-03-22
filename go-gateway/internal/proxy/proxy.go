package proxy

import (
	"encoding/json"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
)

// New builds an httputil.ReverseProxy that forwards requests to upstream,
// stripping prefixToStrip from the path before forwarding.
//
// Example: upstream="https://accounts-service.fly.dev", prefixToStrip="/api/accounts"
//   /api/accounts/api/v1/accounts → https://accounts-service.fly.dev/api/v1/accounts
func New(upstream, prefixToStrip string) http.Handler {
	target, err := url.Parse(upstream)
	if err != nil {
		panic("go-gateway: invalid upstream URL: " + upstream)
	}

	rp := &httputil.ReverseProxy{
		Director: func(req *http.Request) {
			req.URL.Scheme = target.Scheme
			req.URL.Host = target.Host
			req.Host = target.Host

			// Strip the gateway-specific prefix so the upstream sees its own paths.
			req.URL.Path = strings.TrimPrefix(req.URL.Path, prefixToStrip)
			if req.URL.Path == "" {
				req.URL.Path = "/"
			}

			// Standard forwarding headers.
			if clientIP := req.RemoteAddr; clientIP != "" {
				req.Header.Set("X-Forwarded-For", clientIP)
			}
			req.Header.Set("X-Forwarded-Host", req.Host)
		},

		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			_ = json.NewEncoder(w).Encode(map[string]string{
				"code":    "UPSTREAM_ERROR",
				"message": err.Error(),
			})
		},
	}

	return rp
}
