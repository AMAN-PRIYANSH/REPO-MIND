// F3 look-alike, feasible. No code assigns client.Cache directly, but main sets it through
// reflection on a pointer to the struct, so c.Cache != nil holds and flushCache calls Parse.
// The filter must not claim the field is never set. Truth: REACHABLE.
package main

import (
	"fmt"
	"os"
	"reflect"

	"vtfeas/vulnlib"
)

type client struct {
	Name  string
	Cache map[string]string
}

//go:noinline
func (c *client) get(key string) string {
	if c.Cache != nil {
		c.flushCache()
	}
	return c.Name + ":" + key
}

//go:noinline
func (c *client) flushCache() { fmt.Println(vulnlib.Parse(c.Name)) }

func main() {
	c := &client{Name: os.Args[0]}
	reflect.ValueOf(c).Elem().FieldByName("Cache").Set(reflect.ValueOf(map[string]string{"k": "v"}))
	fmt.Println(c.get("k"))
}
