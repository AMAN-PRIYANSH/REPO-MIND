// Package private_helper: an exported function calls an unexported helper.
package private_helper

func Parse(s string) int { return parse(s) }

func parse(s string) int { return len(s) }
