//go:build vtexcluded

package main

import "vtfixtures/vulnlib"

func init() {
	_ = vulnlib.Parse("a b")
}
