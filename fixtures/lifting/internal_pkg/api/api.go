// Package api is the public face of internal/core.
package api

import "vtlift/internal_pkg/internal/core"

func Public() int { return core.Core() }
