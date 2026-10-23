// Package generic_seed: a generic function as the seed (unsupported), and a generic exported
// caller of an ordinary private function (a valid entry point).
package generic_seed

func Map[T any](xs []T) []T { return xs }

func priv() int { return 12 }

func Each[T any](xs []T) int { return len(xs) + priv() }
