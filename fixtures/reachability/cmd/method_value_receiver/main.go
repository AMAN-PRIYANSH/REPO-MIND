package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

func main() {
	var i vulnlib.Impl
	fmt.Println(i.Run("a b"))
}
