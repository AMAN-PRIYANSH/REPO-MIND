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
