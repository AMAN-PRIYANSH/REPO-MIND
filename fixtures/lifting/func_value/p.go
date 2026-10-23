// Package func_value: the seed is reached through a function value stored in a table.
package func_value

var table = map[string]func() int{"a": step}

func step() int { return 2 }

func Dispatch(k string) int { return table[k]() }
