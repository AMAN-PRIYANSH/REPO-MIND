package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

// neverCalled is not called from anywhere.
func neverCalled() string {
	return vulnlib.Parse("a b")
}

func main() {
	fmt.Println(vulnlib.Safe("a b"))
}
