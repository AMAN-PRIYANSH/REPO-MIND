package main

import (
	"fmt"
	"os"

	"vtfixtures/vulnlib"
)

func main() {
	handlers := map[string]func(string) string{
		"parse": vulnlib.Parse,
		"safe":  vulnlib.Safe,
	}
	key := "parse"
	if len(os.Args) > 1 {
		key = os.Args[1]
	}
	if h, ok := handlers[key]; ok {
		fmt.Println(h("a b"))
	}
}
