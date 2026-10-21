package main

import (
	"fmt"
	"unsafe"

	"vtfixtures/vulnlib"
)

func main() {
	f := vulnlib.Parse
	p := unsafe.Pointer(&f)
	g := *(*func(string) string)(p)
	fmt.Println(g("a b"))
}
