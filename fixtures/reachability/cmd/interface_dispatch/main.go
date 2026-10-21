package main

import (
	"fmt"
	"os"

	"vtfixtures/vulnlib"
)

type runner interface{ Run(string) string }

type worker struct{}

func (worker) Run(s string) string { return vulnlib.Parse(s) }

type quiet struct{}

func (quiet) Run(s string) string { return s }

func main() {
	var r runner = worker{}
	if len(os.Args) > 5 {
		r = quiet{}
	}
	fmt.Println(r.Run("a b"))
}
