// Package closure: the seed is called from a closure inside an exported function.
package closure

func inner() int { return 11 }

func Run() func() int {
	return func() int { return inner() }
}
