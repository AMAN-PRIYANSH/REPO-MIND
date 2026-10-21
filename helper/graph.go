package main

import "sort"

// graph is a call graph reduced to what path search and edge checks need.
// Node and edge order is fixed at construction (sorted), so results are deterministic.
type graph struct {
	nodes []node
	out   [][]gEdge
	index map[string][]int // full name -> node ids (normally one)
}

type node struct {
	Pkg, Sym string
}

func (n node) Name() string {
	if n.Pkg == "" {
		return n.Sym
	}
	return n.Pkg + "." + n.Sym
}

type gEdge struct {
	From, To int
	Site     Site
	Kind     string
}

// graphBuilder collects nodes by a unique key and edges, then freezes them in sorted order.
type graphBuilder struct {
	keys  []string
	nodes []node
	ids   map[string]int
	edges []gEdge
}

func newGraphBuilder() *graphBuilder { return &graphBuilder{ids: map[string]int{}} }

// node returns the id for a unique key (several keys may share a display name).
func (b *graphBuilder) node(key string, n node) int {
	if id, ok := b.ids[key]; ok {
		return id
	}
	id := len(b.nodes)
	b.ids[key] = id
	b.keys = append(b.keys, key)
	b.nodes = append(b.nodes, n)
	return id
}

func (b *graphBuilder) edge(from, to int, site Site, kind string) {
	b.edges = append(b.edges, gEdge{From: from, To: to, Site: site, Kind: kind})
}

// freeze renumbers nodes by (name, key) and sorts and de-duplicates edges.
func (b *graphBuilder) freeze() (*graph, map[string]int) {
	order := make([]int, len(b.nodes))
	for i := range order {
		order[i] = i
	}
	sort.Slice(order, func(i, j int) bool {
		ni, nj := b.nodes[order[i]].Name(), b.nodes[order[j]].Name()
		if ni != nj {
			return ni < nj
		}
		return b.keys[order[i]] < b.keys[order[j]]
	})
	remap := make([]int, len(b.nodes))
	g := &graph{nodes: make([]node, len(b.nodes)), out: make([][]gEdge, len(b.nodes)), index: map[string][]int{}}
	for newID, oldID := range order {
		remap[oldID] = newID
		g.nodes[newID] = b.nodes[oldID]
		name := b.nodes[oldID].Name()
		g.index[name] = append(g.index[name], newID)
	}
	seen := map[gEdge]bool{}
	for _, e := range b.edges {
		e.From, e.To = remap[e.From], remap[e.To]
		if !seen[e] {
			seen[e] = true
			g.out[e.From] = append(g.out[e.From], e)
		}
	}
	for _, es := range g.out {
		sort.Slice(es, func(i, j int) bool { return edgeLess(g, es[i], es[j]) })
	}
	ids := map[string]int{}
	for k, old := range b.ids {
		ids[k] = remap[old]
	}
	return g, ids
}

func edgeLess(g *graph, a, b gEdge) bool {
	if a.To != b.To {
		return a.To < b.To
	}
	if a.Site.File != b.Site.File {
		return a.Site.File < b.Site.File
	}
	if a.Site.Line != b.Site.Line {
		return a.Site.Line < b.Site.Line
	}
	return a.Kind < b.Kind
}

func (g *graph) edgeCount() int {
	n := 0
	for _, es := range g.out {
		n += len(es)
	}
	return n
}

// foundPath is a path from root; edges are in call order (root first) and may be empty.
type foundPath struct {
	Root  int
	Edges []gEdge
}

// shortestPaths runs a multi-source BFS from roots and returns the length of the shortest
// path to any target node and up to k distinct paths of that length. found is false when
// no target is reachable. Path length is unbounded here; the caller decides whether to
// report long paths.
func shortestPaths(g *graph, roots []int, targets map[int]bool, k int) (length int, paths []foundPath, found bool) {
	dist := make([]int, len(g.nodes))
	for i := range dist {
		dist[i] = -1
	}
	preds := make([][]gEdge, len(g.nodes))
	queue := []int{}
	for _, r := range roots {
		if dist[r] < 0 {
			dist[r] = 0
			queue = append(queue, r)
		}
	}
	best := -1
	for len(queue) > 0 {
		n := queue[0]
		queue = queue[1:]
		if best >= 0 && dist[n] >= best {
			continue
		}
		for _, e := range g.out[n] {
			switch {
			case dist[e.To] < 0:
				dist[e.To] = dist[n] + 1
				preds[e.To] = append(preds[e.To], e)
				queue = append(queue, e.To)
			case dist[e.To] == dist[n]+1:
				preds[e.To] = append(preds[e.To], e)
			}
			if targets[e.To] && (best < 0 || dist[e.To] < best) {
				best = dist[e.To]
			}
		}
	}
	// A root that is itself a target is a zero-length path.
	for _, r := range roots {
		if targets[r] {
			best = 0
		}
	}
	if best < 0 {
		return 0, nil, false
	}
	var ends []int
	for t := range targets {
		if dist[t] == best {
			ends = append(ends, t)
		}
	}
	sort.Ints(ends)
	var walk func(n int, suffix []gEdge)
	walk = func(n int, suffix []gEdge) {
		if len(paths) >= k {
			return
		}
		if dist[n] == 0 {
			p := make([]gEdge, len(suffix))
			for i := range suffix {
				p[i] = suffix[len(suffix)-1-i]
			}
			paths = append(paths, foundPath{Root: n, Edges: p})
			return
		}
		for _, e := range preds[n] {
			walk(e.From, append(suffix, e))
			if len(paths) >= k {
				return
			}
		}
	}
	for _, t := range ends {
		walk(t, nil)
	}
	return best, paths, true
}

// targetResult turns a path search into a TargetResult.
func targetResult(g *graph, t Target, roots []int, targetIDs []int, limits Limits) TargetResult {
	res := TargetResult{Target: t, Paths: []CallPath{}, MatchedFunctions: []string{}}
	set := map[int]bool{}
	for _, id := range targetIDs {
		set[id] = true
		res.MatchedFunctions = append(res.MatchedFunctions, g.nodes[id].Name())
	}
	sort.Strings(res.MatchedFunctions)
	length, paths, found := shortestPaths(g, roots, set, limits.MaxPathsPerTarget)
	if !found {
		res.Result = ResultNoPath
		return res
	}
	res.Result = ResultPathFound
	res.ShortestLength = &length
	if length > limits.MaxPathLength {
		// Never turn a long path into NO_PATH: report it as found, without the edges.
		reason := "MAX_PATH_LENGTH"
		res.PathsOmitted = &reason
		return res
	}
	for _, p := range paths {
		res.Paths = append(res.Paths, toCallPath(g, t, p))
	}
	return res
}

func toCallPath(g *graph, t Target, p foundPath) CallPath {
	cp := CallPath{Target: t, Edges: []PathEdge{}}
	cp.Entry = Target{Package: g.nodes[p.Root].Pkg, Symbol: g.nodes[p.Root].Sym}
	for _, e := range p.Edges {
		cp.Edges = append(cp.Edges, PathEdge{
			Caller: g.nodes[e.From].Name(), Callee: g.nodes[e.To].Name(), CallSite: e.Site, Kind: e.Kind,
		})
	}
	return cp
}
