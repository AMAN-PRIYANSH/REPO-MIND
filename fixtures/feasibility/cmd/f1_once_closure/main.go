// F1, infeasible, two levels of parameter pass-through (the sync.Once pattern of CP7b).
// once.Do(f) passes f on to doSlow(f), which calls f(). VTA joins both closures given to Do at
// that call. main reaches Do only through setup(), which passes setup's own closure; the closure
// that calls Parse is passed only in dangerous(), under `if c.hook != nil`, and no code ever
// assigns config.hook (an F3 step). Truth: Parse never runs.
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

type config struct {
	name string
	hook func(string)
}

//go:noinline
func setup() { a.Do(func() { fmt.Println("setup") }) }

//go:noinline
func dangerous(c *config) {
	if c.hook != nil {
		b.Do(func() { fmt.Println(vulnlib.Parse(c.name)) })
	}
}

func main() {
	setup()
	dangerous(&config{name: "x"})
}
