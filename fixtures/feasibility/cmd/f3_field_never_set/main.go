// F3, infeasible (the archives Rar.FS pattern of CP7b). Rar.Extract calls fileSystem (which calls
// Parse) only if r.FS != nil. Rar values are registered as zero values in an interface slice and
// no code assigns Rar.FS. Truth: Parse never runs.
package main

import (
	"fmt"

	"vtfeas/vulnlib"
)

type Opener interface{ Open(name string) string }

type Format interface{ Extract(name string) string }

type Rar struct {
	Password string
	FS       Opener
}

//go:noinline
func (r Rar) Extract(name string) string {
	opts := []string{name}
	if r.Password != "" {
		opts = append(opts, "password")
	}
	if r.FS != nil {
		opts = append(opts, fileSystem(r.FS))
	}
	return fmt.Sprint(opts)
}

//go:noinline
func fileSystem(o Opener) string { return vulnlib.Parse(fmt.Sprint(o)) }

var formats = []Format{Rar{}}

func main() {
	for _, f := range formats {
		fmt.Println(f.Extract("a.rar"))
	}
}
