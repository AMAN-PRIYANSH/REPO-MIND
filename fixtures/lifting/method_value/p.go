// Package method_value: the seed is reached through a method value (t.work stored, then called).
package method_value

type tool struct{}

func (tool) work() int { return 3 }

func Use() int {
	t := tool{}
	m := t.work
	return m()
}
