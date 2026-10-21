package main

import (
	"reflect"
	"testing"
)

// buildTestGraph adds edges "a->b@line" between named nodes in the given order.
func buildTestGraph(edges [][3]any) (*graph, map[string]int) {
	b := newGraphBuilder()
	for _, e := range edges {
		from := b.node(e[0].(string), node{Pkg: "p", Sym: e[0].(string)})
		to := b.node(e[1].(string), node{Pkg: "p", Sym: e[1].(string)})
		b.edge(from, to, Site{File: "f.go", Line: e[2].(int)}, KindStatic)
	}
	g, keys := b.freeze()
	return g, keys
}

func pathNames(g *graph, paths []foundPath) [][]string {
	var out [][]string
	for _, p := range paths {
		names := []string{g.nodes[p.Root].Sym}
		for _, e := range p.Edges {
			names = append(names, g.nodes[e.To].Sym)
		}
		out = append(out, names)
	}
	return out
}

var diamond = [][3]any{
	{"main", "a", 1}, {"main", "b", 2}, {"a", "vuln", 3}, {"b", "vuln", 4},
	{"main", "c", 5}, {"c", "d", 6}, {"d", "vuln", 7}, {"vuln", "main", 8}, // cycle back
}

func TestShortestPathsAllMinimalAndLimited(t *testing.T) {
	g, id := buildTestGraph(diamond)
	targets := map[int]bool{id["vuln"]: true}
	n, paths, found := shortestPaths(g, []int{id["main"]}, targets, 3)
	if !found || n != 2 {
		t.Fatalf("found=%v length=%d", found, n)
	}
	want := [][]string{{"main", "a", "vuln"}, {"main", "b", "vuln"}}
	if got := pathNames(g, paths); !reflect.DeepEqual(got, want) {
		t.Fatalf("paths %v; want %v (the length-3 path via c, d must not appear)", got, want)
	}
	_, paths, _ = shortestPaths(g, []int{id["main"]}, targets, 1)
	if len(paths) != 1 {
		t.Fatalf("k=1 gave %d paths", len(paths))
	}
}

func TestShortestPathsDeterministicRegardlessOfInsertionOrder(t *testing.T) {
	rev := make([][3]any, len(diamond))
	for i := range diamond {
		rev[i] = diamond[len(diamond)-1-i]
	}
	g1, id1 := buildTestGraph(diamond)
	g2, id2 := buildTestGraph(rev)
	_, p1, _ := shortestPaths(g1, []int{id1["main"]}, map[int]bool{id1["vuln"]: true}, 3)
	_, p2, _ := shortestPaths(g2, []int{id2["main"]}, map[int]bool{id2["vuln"]: true}, 3)
	if !reflect.DeepEqual(pathNames(g1, p1), pathNames(g2, p2)) {
		t.Fatalf("order-dependent: %v vs %v", pathNames(g1, p1), pathNames(g2, p2))
	}
}

func TestNoPathAndRootAsTarget(t *testing.T) {
	g, id := buildTestGraph([][3]any{{"main", "a", 1}, {"other", "vuln", 2}})
	if _, _, found := shortestPaths(g, []int{id["main"]}, map[int]bool{id["vuln"]: true}, 3); found {
		t.Fatal("found a path to an unreachable node")
	}
	n, paths, found := shortestPaths(g, []int{id["main"]}, map[int]bool{id["main"]: true}, 3)
	if !found || n != 0 || len(paths) != 1 || len(paths[0].Edges) != 0 || paths[0].Root != id["main"] {
		t.Fatalf("root-as-target: found=%v n=%d paths=%v", found, n, paths)
	}
}

func TestMultipleRootsAndCallSites(t *testing.T) {
	g, id := buildTestGraph([][3]any{{"init", "x", 1}, {"x", "vuln", 2}, {"main", "vuln", 3}, {"main", "vuln", 4}})
	roots := []int{id["init"], id["main"]}
	n, paths, _ := shortestPaths(g, roots, map[int]bool{id["vuln"]: true}, 5)
	if n != 1 || len(paths) != 2 || paths[0].Edges[0].Site.Line != 3 || paths[1].Edges[0].Site.Line != 4 {
		t.Fatalf("n=%d paths=%+v; want the two direct call sites from main", n, paths)
	}
}

func TestTargetResultNeverTurnsLongPathIntoNoPath(t *testing.T) {
	g, id := buildTestGraph(diamond)
	tgt := Target{Package: "p", Symbol: "vuln"}
	r := targetResult(g, tgt, []int{id["main"]}, []int{id["vuln"]}, Limits{MaxPathsPerTarget: 3, MaxPathLength: 1})
	if r.Result != ResultPathFound || r.PathsOmitted == nil || *r.PathsOmitted != "MAX_PATH_LENGTH" || len(r.Paths) != 0 {
		t.Fatalf("got %+v", r)
	}
	r = targetResult(g, tgt, []int{id["main"]}, []int{id["vuln"]}, Limits{MaxPathsPerTarget: 3, MaxPathLength: 40})
	if r.Result != ResultPathFound || len(r.Paths) != 2 || r.Paths[0].Entry.Symbol != "main" ||
		r.Paths[0].Edges[0].Caller != "p.main" || r.Paths[0].Edges[1].Callee != "p.vuln" {
		t.Fatalf("got %+v", r)
	}
	r = targetResult(g, tgt, []int{id["main"]}, nil, Limits{MaxPathsPerTarget: 3, MaxPathLength: 40})
	if r.Result != ResultNoPath || len(r.Paths) != 0 {
		t.Fatalf("no target nodes: got %+v", r)
	}
}

func TestCheckEdges(t *testing.T) {
	g, _ := buildTestGraph(diamond)
	res := checkEdges(g, []EdgeQuery{
		{Caller: "p.main", Callee: "p.a"},
		{Caller: "p.main", Callee: "p.a", CallSite: &Site{File: "f.go", Line: 1}},
		{Caller: "p.main", Callee: "p.a", CallSite: &Site{File: "f.go", Line: 9}},
		{Caller: "p.a", Callee: "p.main"},
		{Caller: "p.zzz", Callee: "p.a"},
	})
	want := []bool{true, true, false, false, false}
	for i, r := range res {
		if r.Exists != want[i] {
			t.Errorf("query %d: exists=%v; want %v (%+v)", i, r.Exists, want[i], r)
		}
	}
	if res[4].CallerFound || !res[4].CalleeFound {
		t.Errorf("caller/callee found flags wrong: %+v", res[4])
	}
}
