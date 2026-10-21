package main

import (
	"fmt"
	"sync"

	"vtfixtures/vulnlib"
)

func main() {
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		fmt.Println(vulnlib.Parse("a b"))
	}()
	wg.Wait()
}
