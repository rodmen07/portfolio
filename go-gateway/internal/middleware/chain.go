package middleware

import "net/http"

// Chain wraps handler with middlewares applied outermost-first.
// chain(h, A, B, C) → A(B(C(h)))
func Chain(h http.Handler, middlewares ...func(http.Handler) http.Handler) http.Handler {
	for i := len(middlewares) - 1; i >= 0; i-- {
		h = middlewares[i](h)
	}
	return h
}
