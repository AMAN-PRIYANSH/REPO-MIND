// Out of scope (the go-pkcs12 pattern of CP7b): the MAC algorithm comes from a field of a
// package-level encoder value, not from a parameter or a never-set field. computeMac calls
// doPBMAC1 (which calls Parse) only for "pbmac1", and no encoder uses it, so Parse never runs
// (truth NOT_REACHABLE). F1-F3 do not cover this, so the filter must leave the verdict REACHABLE:
// this case measures a known miss, not a false downgrade.
package main

import (
	"fmt"

	"vtfeas/vulnlib"
)

type Encoder struct{ macAlgorithm string }

var Modern = &Encoder{macAlgorithm: "sha256"}

var Legacy = &Encoder{macAlgorithm: "sha1"}

//go:noinline
func (e *Encoder) Encode(data string) string { return computeMac(e.macAlgorithm, data) }

//go:noinline
func computeMac(alg, data string) string {
	if alg == "pbmac1" {
		return doPBMAC1(data)
	}
	return alg + ":" + data
}

//go:noinline
func doPBMAC1(data string) string { return vulnlib.Parse(data) }

func main() {
	fmt.Println(Modern.Encode("a"), Legacy.Encode("b"))
}
