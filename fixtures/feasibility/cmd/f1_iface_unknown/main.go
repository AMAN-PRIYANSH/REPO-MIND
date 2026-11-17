// F1 look-alike, feasible. emit's w.Write is joined to *os.File.Write and evil.Write. The second
// call passes a package variable, whose dynamic type the filter cannot know, so the step must
// count as feasible; at run time the variable holds evil{}, so Parse runs. Truth: REACHABLE.
package main

import (
	"os"

	"vtfeas/vulnlib"
)

type sink interface{ Write(p []byte) (int, error) }

type evil struct{}

func (evil) Write(p []byte) (int, error) { return len(vulnlib.Parse(string(p))), nil }

var out sink = evil{}

//go:noinline
func emit(w sink, s string) { w.Write([]byte(s)) }

func main() {
	emit(os.Stdout, "hello\n")
	emit(out, "to the variable")
}
