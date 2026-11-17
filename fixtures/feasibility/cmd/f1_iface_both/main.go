// F1 look-alike, feasible. Same shape as f1_iface_splice, but report() is called with a value
// that depends on the command line, so emit(evil{}, ...) can run and evil.Write calls Parse.
// The path through main -> emit(os.Stdout) is infeasible, but another path runs. Truth: REACHABLE.
package main

import (
	"os"

	"vtfeas/vulnlib"
)

type sink interface{ Write(p []byte) (int, error) }

type evil struct{}

func (evil) Write(p []byte) (int, error) { return len(vulnlib.Parse(string(p))), nil }

//go:noinline
func emit(w sink, s string) { w.Write([]byte(s)) }

//go:noinline
func report(verbose bool) {
	if verbose {
		emit(evil{}, "report")
	}
}

func main() {
	emit(os.Stdout, "hello\n")
	report(len(os.Args) > 1)
}
