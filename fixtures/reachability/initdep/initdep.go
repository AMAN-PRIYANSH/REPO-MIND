// Package initdep calls the vulnerable function from init().
package initdep

import "vtfixtures/vulnlib"

var Result string

func init() {
	Result = vulnlib.Parse("init")
}
