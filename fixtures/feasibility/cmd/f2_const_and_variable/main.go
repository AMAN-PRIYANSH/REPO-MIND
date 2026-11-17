// F2 look-alike, feasible. Same listen() as f2_const_port; one caller passes the constant 0, but
// a second caller passes a port read from the command line, so serveH3 can run. Truth: REACHABLE.
package main

import (
	"fmt"
	"os"

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

func main() {
	listen("/run/app.sock", 0)
	listen("0.0.0.0", len(os.Args)*443)
}
