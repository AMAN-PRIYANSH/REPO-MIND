package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

// echo is the second implementation of vulnlib.Runner. vulnlib.Impl is the
// first; its Run calls the vulnerable function.
type echo struct{}

func (echo) Run(s string) string { return s }

// newRunner always returns echo{}. Getting r from a function keeps r.Run an
// interface call instead of letting the compiler devirtualize it.
func newRunner() vulnlib.Runner { return echo{} }

func main() {
	r := newRunner()
	// The type assertion names vulnlib.Impl, but no vulnlib.Impl value is ever
	// created, so it always fails.
	if _, ok := r.(vulnlib.Impl); ok {
		fmt.Println("impl")
	}
	fmt.Println(r.Run("a b"))
}
