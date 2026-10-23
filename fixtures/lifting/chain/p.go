// Package chain: a long chain of private functions below one exported function (depth limit).
package chain

func a() int { return 1 }
func b() int { return a() }
func c() int { return b() }
func d() int { return c() }

func Top() int { return d() }
