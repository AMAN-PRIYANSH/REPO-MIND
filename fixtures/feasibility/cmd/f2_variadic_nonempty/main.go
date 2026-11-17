// F2 look-alike, feasible. Same exec/execSimple as f2_variadic_empty, but one call passes one
// variadic argument, so len(args) > 0 holds and sanitize calls Parse. Truth: REACHABLE.
package main

import (
	"fmt"

	"vtfeas/vulnlib"
)

//go:noinline
func exec(sql string, args ...any) string { return execSimple(sql, args) }

//go:noinline
func execSimple(sql string, args []any) string {
	if len(args) > 0 {
		sql = sanitize(sql, args)
	}
	return sql
}

//go:noinline
func sanitize(sql string, args []any) string { return vulnlib.Parse(fmt.Sprint(sql, args)) }

func main() {
	fmt.Println(exec("CREATE DATABASE app"))
	fmt.Println(exec("SELECT $1", 42))
}
