package main

import (
	"testing"

	"vtfixtures/vulnlib"
)

func TestParse(t *testing.T) {
	_ = vulnlib.Parse("a b")
}
