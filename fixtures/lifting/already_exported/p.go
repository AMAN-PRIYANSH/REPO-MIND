// Package already_exported: the seed is itself an exported function.
package already_exported

func Parse(s string) int { return helper(s) }

func helper(s string) int { return len(s) }
