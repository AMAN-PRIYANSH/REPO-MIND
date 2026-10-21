package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

func main() {
	// Method expression: f has type func(vulnlib.Impl, string) string.
	f := vulnlib.Impl.Run
	fmt.Println(f(vulnlib.Impl{}, "a b"))
}
