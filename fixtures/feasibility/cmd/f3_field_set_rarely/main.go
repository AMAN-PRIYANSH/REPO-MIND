// F3 look-alike, feasible. Same Rar.Extract as f3_field_never_set, but withFS() sets Rar.FS and is
// called when the command line has more than three arguments, so fileSystem can run.
// Truth: REACHABLE.
package main

import (
	"fmt"
	"os"

	"vtfeas/vulnlib"
)

type Opener interface{ Open(name string) string }

type Format interface{ Extract(name string) string }

type dirFS string

func (d dirFS) Open(name string) string { return string(d) + "/" + name }

type Rar struct {
	Password string
	FS       Opener
}

//go:noinline
func (r Rar) Extract(name string) string {
	opts := []string{name}
	if r.FS != nil {
		opts = append(opts, fileSystem(r.FS))
	}
	return fmt.Sprint(opts)
}

//go:noinline
func fileSystem(o Opener) string { return vulnlib.Parse(o.Open("x")) }

//go:noinline
func withFS(dir string) Rar { return Rar{FS: dirFS(dir)} }

func main() {
	formats := []Format{Rar{}}
	if len(os.Args) > 3 {
		formats = append(formats, withFS(os.Args[3]))
	}
	for _, f := range formats {
		fmt.Println(f.Extract("a.rar"))
	}
}
