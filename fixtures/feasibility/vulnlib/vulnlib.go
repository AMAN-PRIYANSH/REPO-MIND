// Package vulnlib is the fake vulnerable library of the CP9 feasibility fixtures.
// Parse is the "vulnerable" function; every case targets vtfeas/vulnlib.Parse.
package vulnlib

import "strings"

// Parse is the vulnerable function. It is marked noinline so the linker method keeps it as a
// symbol whenever some code calls it.
//
//go:noinline
func Parse(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] == ' ' {
			b.WriteByte('_')
			continue
		}
		b.WriteByte(s[i])
	}
	return "parsed:" + b.String()
}
