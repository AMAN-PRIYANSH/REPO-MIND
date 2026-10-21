package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

type runner interface{ Run(string) string }

// loud.Run calls the vulnerable function.
type loud struct{}

func (loud) Run(s string) string { return vulnlib.Parse(s) }

// quiet has a Run method with the same name and signature.
type quiet struct{}

func (quiet) Run(s string) string { return s }

// keep holds a loud value in an `any`, so loud and its method set are in the
// binary. It is only printed with %T, which reads the type name and calls no
// method.
var keep any = loud{}

// newRunner always returns quiet{}. Getting r from a function keeps r.Run an
// interface call: with `var r runner = quiet{}` in main the compiler
// devirtualizes r.Run to quiet.Run (seen with -gcflags=-m).
func newRunner() runner { return quiet{} }

func main() {
	r := newRunner()
	fmt.Println(r.Run("a b"))
	fmt.Printf("%T\n", keep)
}
