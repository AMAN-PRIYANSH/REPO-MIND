package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

// stored receives a closure that calls the vulnerable function. Nothing ever
// calls stored.
var stored func(string) string

func main() {
	stored = func(s string) string { return vulnlib.Parse(s) }
	fmt.Println(stored != nil)
	fmt.Println(vulnlib.Safe("a b"))
}
