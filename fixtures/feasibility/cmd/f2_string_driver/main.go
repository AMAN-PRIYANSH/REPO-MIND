// F2, infeasible (a hard-coded driver name). open() picks a driver by a string switch; the only
// caller passes the constant "badgerv2", so the "postgresql" branch, which calls Parse, never runs.
// Truth: Parse never runs.
package main

import (
	"fmt"

	"vtfeas/vulnlib"
)

//go:noinline
func open(driver, dsn string) string {
	switch driver {
	case "badgerv2":
		return "badger:" + dsn
	case "postgresql":
		return postgres(dsn)
	}
	return ""
}

//go:noinline
func postgres(dsn string) string { return vulnlib.Parse(dsn) }

func main() { fmt.Println(open("badgerv2", "/var/lib/db")) }
