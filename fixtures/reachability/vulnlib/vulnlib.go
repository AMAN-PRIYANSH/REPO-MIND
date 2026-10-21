// Package vulnlib is a fake vulnerable library used as the target of the
// reachability fixtures. Parse is the "vulnerable" function.
package vulnlib

import "strings"

// Parse is the vulnerable function. It is large enough, and marked noinline,
// that the compiler does not inline it at call sites.
//
//go:noinline
func Parse(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] == ' ' {
			b.WriteByte('_')
			continue
		}
		b.WriteByte(s[i])
	}
	return "parsed:" + b.String()
}

// ParseTiny is the vulnerable function in the inlining fixture. Its body is
// small enough for the compiler to inline it at call sites.
func ParseTiny(s string) string { return "tiny:" + s }

// ParseAny is a generic vulnerable function (used by the generic-target case).
func ParseAny[T any](v T) string { return Parse(strings.TrimSpace(strings.Repeat("x", 1))) }

// Safe is a function in the same package that is not vulnerable.
func Safe(s string) string { return strings.ToUpper(s) }

// Runner is implemented by types that run a payload.
type Runner interface {
	Run(s string) string
}

// Impl has a value-receiver method that calls the vulnerable function.
type Impl struct{}

// Run calls Parse.
func (Impl) Run(s string) string { return Parse(s) }

// PImpl has a pointer-receiver method that calls the vulnerable function.
type PImpl struct{}

// Run calls Parse.
func (*PImpl) Run(s string) string { return Parse(s) }
