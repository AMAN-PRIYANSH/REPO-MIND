package main

import (
	"fmt"

	"vtfixtures/vulnlib"
)

func apply[T any](v T, f func(T) string) string { return f(v) }

func viaGeneric[T ~string](v T) string { return vulnlib.Parse(string(v)) }

func main() {
	fmt.Println(apply("a b", viaGeneric[string]))
}
