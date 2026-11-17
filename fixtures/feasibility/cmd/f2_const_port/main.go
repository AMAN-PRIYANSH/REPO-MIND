// F2, infeasible (the ListenUnix pattern of CP7b). listen() starts serveH3 only when port != 0.
// Its only caller, listenUnix, reaches it through a function value from a map and passes the
// constant 0. Truth: Parse never runs.
package main

import (
	"fmt"

	"vtfeas/vulnlib"
)

//go:noinline
func listen(addr string, port int) {
	if port == 0 {
		fmt.Println("unix socket", addr)
	} else {
		go serveH3(addr, port)
	}
}

//go:noinline
func serveH3(addr string, port int) { fmt.Println(vulnlib.Parse(addr), port) }

var listeners = map[string]func(string, int){"xhttp": listen}

//go:noinline
func listenUnix(addr string) { listeners["xhttp"](addr, 0) }

func main() { listenUnix("/run/app.sock") }
