// F3 look-alike, feasible. client.cache is never assigned by a direct field store, but its address
// is passed to configure(), which stores through the pointer, so c.cache != nil holds and
// flushCache calls Parse. The filter must treat the escaped address as unknown. Truth: REACHABLE.
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
func configure(m *map[string]string) { *m = map[string]string{"warm": "yes"} }

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
	configure(&c.cache)
	fmt.Println(c.get("k"))
}
