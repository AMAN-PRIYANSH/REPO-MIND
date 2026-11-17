// F1 look-alike, feasible. Same once.Do / doSlow shape as f1_once_closure, but the closure that
// calls Parse is passed to Do unconditionally from main. Truth: REACHABLE.
package main

import (
	"fmt"

	"vtfeas/vulnlib"
)

type once struct{ done bool }

//go:noinline
func (o *once) Do(f func()) {
	if !o.done {
		o.doSlow(f)
	}
}

//go:noinline
func (o *once) doSlow(f func()) {
	o.done = true
	f()
}

var a, b once

//go:noinline
func setup() { a.Do(func() { fmt.Println("setup") }) }

func main() {
	setup()
	b.Do(func() { fmt.Println(vulnlib.Parse("now")) })
}
