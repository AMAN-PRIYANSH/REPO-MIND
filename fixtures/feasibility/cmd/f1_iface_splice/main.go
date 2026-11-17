// F1, infeasible. emit's w.Write is joined by VTA to *os.File.Write and evil.Write, because two
// call sites pass those types. main's call passes os.Stdout, so on the shortest path the dynamic
// step to evil.Write cannot run. The only call that passes evil{} is in report(), under
// `if verbose`, and report is called only with the constant false (an F2 step). Truth: Parse never
// runs.
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
	report(false)
}
