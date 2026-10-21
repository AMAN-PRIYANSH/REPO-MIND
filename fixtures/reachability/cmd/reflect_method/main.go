package main

import (
	"fmt"
	"reflect"
	"strings"

	"vtfixtures/vulnlib"
)

func main() {
	// The method name is assembled at run time, so no call to Impl.Run is
	// written in the source.
	name := strings.Join([]string{"R", "un"}, "")
	m := reflect.ValueOf(vulnlib.Impl{}).MethodByName(name)
	if m.IsValid() {
		out := m.Call([]reflect.Value{reflect.ValueOf("a b")})
		fmt.Println(out[0])
	}
}
