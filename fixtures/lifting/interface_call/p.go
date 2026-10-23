// Package interface_call: the seed is a method of an unexported type reached through an interface.
package interface_call

type runner interface{ run() int }

type impl struct{}

func (impl) run() int { return 1 }

func Do() int {
	var r runner = impl{}
	return r.run()
}
