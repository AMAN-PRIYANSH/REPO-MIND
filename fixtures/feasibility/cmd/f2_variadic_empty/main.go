// F2, infeasible (the pgx Exec pattern of CP7b). exec passes its variadic arguments on to
// execSimple, which sanitizes (and calls Parse) only if len(args) > 0. The only call passes no
// variadic arguments (a nil slice). Truth: Parse never runs.
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

func main() { fmt.Println(exec("CREATE DATABASE app")) }
