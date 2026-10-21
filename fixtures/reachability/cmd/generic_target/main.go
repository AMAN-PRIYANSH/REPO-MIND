package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

func main() {
	fmt.Println(vulnlib.ParseAny[string]("a b"))
}
