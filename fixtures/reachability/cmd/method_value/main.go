package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

func main() {
	f := vulnlib.Impl{}.Run
	fmt.Println(f("a b"))
}
