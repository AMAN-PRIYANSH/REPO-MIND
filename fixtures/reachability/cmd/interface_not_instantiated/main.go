package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

type runner interface{ Run(string) string }

// worker implements runner and calls the vulnerable function, but no value of
// type worker is ever created.
type worker struct{}

func (worker) Run(s string) string { return vulnlib.Parse(s) }

type quiet struct{}

func (quiet) Run(s string) string { return s }

func main() {
	var r runner = quiet{}
	fmt.Println(r.Run("a b"))
	_ = vulnlib.Safe
}
