// Package root_only: the only caller of the seed is init, so there is no exported caller.
package root_only

var v = orphan()

func orphan() int { return 6 }

func init() { _ = orphan() }

func Unrelated() int { return 7 }
