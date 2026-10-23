// Package unexported_type: an exported method of an unexported type is NOT an entry point;
// the exported function that returns the unexported type's result is.
package unexported_type

type impl struct{}

func (impl) Exported() int { return impl{}.work() }

func (impl) work() int { return 4 }

func Wrap() int { return impl{}.Exported() }
