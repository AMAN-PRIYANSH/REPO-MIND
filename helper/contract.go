package main

// Contract types for the Python-to-Go helper (docs/design/INTERFACES_AND_CONTRACTS.md, section 2).

const ContractVersion = "1.0"

// Error codes written by the helper. Python adds TIMEOUT and HELPER_MISSING.
const (
	CodeBadRequest       = "BAD_REQUEST"
	CodeContractMismatch = "CONTRACT_MISMATCH"
	CodeLoadFailed       = "LOAD_FAILED"
	CodeTypeErrors       = "TYPE_ERRORS"
	CodeTargetNotFound   = "TARGET_NOT_FOUND"
	CodeInternal         = "INTERNAL"
	CodeUnsupportedForm  = "UNSUPPORTED_SYMBOL_FORM"
	CodePackageUnloaded  = "PACKAGE_NOT_LOADED" // lift/callers/callees: the target's package was skipped at load time
)

// Defaults for the CP5b modes.
const (
	defaultMaxLiftDepth = 10
	defaultMaxHops      = 1
	defaultMaxResults   = 200
)

// Lift statuses and rules (open question Q4: both stopping rules are implemented).
const (
	LiftLifted           = "LIFTED"
	LiftAlreadyExported  = "ALREADY_EXPORTED"
	LiftRootOnly         = "ROOT_ONLY"
	LiftNotInProgram     = "PACKAGE_NOT_IN_PROGRAM"
	LiftError            = "ERROR"
	RuleNearest          = "NEAREST"
	RuleAll              = "ALL"
	NeighborFound        = "FOUND"
	NeighborNone         = "NONE"
	NeighborNotInProgram = "PACKAGE_NOT_IN_PROGRAM"
	NeighborError        = "ERROR"
)

// Per-target results of reach and naive.
const (
	ResultPathFound = "PATH_FOUND"
	ResultNoPath    = "NO_PATH"
	ResultError     = "ERROR"
)

// Edge kinds.
const (
	KindStatic  = "STATIC"
	KindDynamic = "DYNAMIC"
)

const (
	defaultMaxPaths      = 3
	defaultMaxPathLength = 40
)

type Target struct {
	Package string `json:"package"`
	Symbol  string `json:"symbol"`
}

type Build struct {
	Tags   []string `json:"tags"`
	GOOS   *string  `json:"goos"`
	GOARCH *string  `json:"goarch"`
}

type Limits struct {
	MaxPathsPerTarget int `json:"max_paths_per_target"`
	MaxPathLength     int `json:"max_path_length"`
	// CP5b (lift, callers, callees); zero means the default below.
	MaxLiftDepth int `json:"max_lift_depth"`
	MaxHops      int `json:"max_hops"`
	MaxResults   int `json:"max_results"`
}

type Site struct {
	File string `json:"file"`
	Line int    `json:"line"`
}

// EdgeQuery asks whether caller -> callee exists; names use the CallPath edge form ("pkgpath.Symbol").
type EdgeQuery struct {
	Caller   string `json:"caller"`
	Callee   string `json:"callee"`
	CallSite *Site  `json:"call_site,omitempty"`
}

type Request struct {
	ContractVersion string      `json:"contract_version"`
	Mode            string      `json:"mode"`
	ModuleDir       string      `json:"module_dir"`
	MainPackages    []string    `json:"main_packages"`
	Targets         []Target    `json:"targets"`
	Build           Build       `json:"build"`
	Limits          Limits      `json:"limits"`
	Files           []string    `json:"files"`
	Edges           []EdgeQuery `json:"edges"`
	// CP5b: library mode (no main_packages) loads these patterns; default ["./..."].
	Packages  []string `json:"packages"`
	LiftRules []string `json:"lift_rules"` // NEAREST and/or ALL; default both
	External  bool     `json:"external"`   // callers/callees: also report functions outside the loaded module
}

type Error struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func (e *Error) Error() string { return e.Code + ": " + e.Message }

func errf(code, msg string) *Error { return &Error{Code: code, Message: msg} }

type Toolchain struct {
	GoVersion     string `json:"go_version"`
	GOOS          string `json:"goos"`
	GOARCH        string `json:"goarch"`
	XToolsVersion string `json:"x_tools_version"`
}

type Stats struct {
	PackagesLoaded int    `json:"packages_loaded"`
	CallgraphNodes int    `json:"callgraph_nodes"`
	CallgraphEdges int    `json:"callgraph_edges"`
	DurationMS     int64  `json:"duration_ms"`
	PeakRSSKB      *int64 `json:"peak_rss_kb"`
}

type Response struct {
	ContractVersion string     `json:"contract_version"`
	OK              bool       `json:"ok"`
	Mode            string     `json:"mode"`
	Toolchain       *Toolchain `json:"toolchain,omitempty"`
	Results         any        `json:"results,omitempty"`
	Stats           *Stats     `json:"stats,omitempty"`
	Error           *Error     `json:"error,omitempty"`
	Load            *LoadInfo  `json:"load,omitempty"`
}

// LoadInfo reports what library-mode loading left out (CP5b): packages whose own errors, or
// whose imports' errors, kept them out of the analysed program. Never hidden, always counted.
type LoadInfo struct {
	Mode            string   `json:"mode"` // LIBRARY or APP
	PackagesMatched int      `json:"packages_matched"`
	PackagesSkipped int      `json:"packages_skipped"`
	FirstErrors     []string `json:"first_errors"`
}

type PathEdge struct {
	Caller   string `json:"caller"`
	Callee   string `json:"callee"`
	CallSite Site   `json:"call_site"`
	Kind     string `json:"kind"`
}

type CallPath struct {
	Entry  Target     `json:"entry"`
	Target Target     `json:"target"`
	Edges  []PathEdge `json:"edges"`
}

// TargetResult is one target's answer in reach and naive mode.
type TargetResult struct {
	Target              Target     `json:"target"`
	Result              string     `json:"result"`
	Paths               []CallPath `json:"paths"`
	ShortestLength      *int       `json:"shortest_length"`
	PathsOmitted        *string    `json:"paths_omitted"`
	MatchedFunctions    []string   `json:"matched_functions"`
	Error               *Error     `json:"error"`
	PackageNotInProgram bool       `json:"package_not_in_program"`
}

type EdgeResult struct {
	Caller      string   `json:"caller"`
	Callee      string   `json:"callee"`
	CallSite    *Site    `json:"call_site"`
	Exists      bool     `json:"exists"`
	CallerFound bool     `json:"caller_found"`
	CalleeFound bool     `json:"callee_found"`
	CallSites   []Site   `json:"call_sites"`
	Kinds       []string `json:"kinds"`
}

type FuncInfo struct {
	Symbol string `json:"symbol"`
	Start  int    `json:"start"`
	End    int    `json:"end"`
}

type FileFuncs struct {
	File      string     `json:"file"`
	Package   string     `json:"package"`
	Functions []FuncInfo `json:"functions"`
}

// LiftEntry is one exported entry point a seed lifts to, with one example call path
// (entry first, seed last). Depth is the number of call edges on that path.
type LiftEntry struct {
	Package string   `json:"package"`
	Symbol  string   `json:"symbol"`
	Depth   int      `json:"depth"`
	Dynamic bool     `json:"dynamic"` // some edge on the example path was resolved dynamically
	Path    CallPath `json:"path"`
}

// LiftRuleResult is the outcome of one stopping rule for one seed.
type LiftRuleResult struct {
	Entries           []LiftEntry `json:"entries"`
	DepthLimitReached bool        `json:"depth_limit_reached"`
}

// LiftResult is one seed's answer in lift mode.
type LiftResult struct {
	Target              Target                    `json:"target"`
	Status              string                    `json:"status"`
	Rules               map[string]LiftRuleResult `json:"rules"`
	MatchedFunctions    []string                  `json:"matched_functions"`
	Error               *Error                    `json:"error"`
	PackageNotInProgram bool                      `json:"package_not_in_program"`
}

// HopEdge is one call-graph edge found by callers/callees; Hop is 1 for a direct neighbour.
type HopEdge struct {
	Hop      int    `json:"hop"`
	Caller   string `json:"caller"`
	Callee   string `json:"callee"`
	CallSite Site   `json:"call_site"`
	Kind     string `json:"kind"`
	// The far end of the edge (the caller for callers, the callee for callees), structured.
	Other Target `json:"other"`
}

// NeighborResult is one target's answer in callers and callees mode.
type NeighborResult struct {
	Target              Target    `json:"target"`
	Result              string    `json:"result"`
	Edges               []HopEdge `json:"edges"`
	Truncated           bool      `json:"truncated"`
	MatchedFunctions    []string  `json:"matched_functions"`
	Error               *Error    `json:"error"`
	PackageNotInProgram bool      `json:"package_not_in_program"`
}
