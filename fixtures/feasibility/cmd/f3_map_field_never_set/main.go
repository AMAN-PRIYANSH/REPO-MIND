// F3, infeasible (a nil map field). client.get calls flushCache (which calls Parse) only if
// c.cache != nil; clients are built with a name only and no code assigns client.cache.
// Truth: Parse never runs.
package main

import (
	"fmt"
	"os"

	"vtfeas/vulnlib"
)

type client struct {
	name  string
	cache map[string]string
}

//go:noinline
func (c *client) get(key string) string {
	if c.cache != nil {
		c.flushCache()
	}
	return c.name + ":" + key
}

//go:noinline
func (c *client) flushCache() { fmt.Println(vulnlib.Parse(c.name)) }

func main() {
	c := &client{name: os.Args[0]}
	fmt.Println(c.get("k"))
}
