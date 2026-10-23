// Package main: the seed is called only from main, which is not an entry point.
package main

func run() int { return 15 }

func Exported() int { return 16 }

func main() { _ = run() }
