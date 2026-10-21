package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

func main() {
	p := &vulnlib.PImpl{}
	fmt.Println(p.Run("a b"))
}
