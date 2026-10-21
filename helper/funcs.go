package main

import (
	"go/ast"
	"go/parser"
	"go/token"
	"path/filepath"
	"strings"
)

// runFuncs lists the functions and methods declared in the given Go files, in source order.
func runFuncs(req *Request) (any, *Error) {
	out := make([]FileFuncs, 0, len(req.Files))
	for _, f := range req.Files {
		name := filepath.FromSlash(strings.ReplaceAll(f, "\\", "/"))
		if !filepath.IsAbs(name) && req.ModuleDir != "" {
			name = filepath.Join(filepath.FromSlash(strings.ReplaceAll(req.ModuleDir, "\\", "/")), name)
		}
		fset := token.NewFileSet()
		file, err := parser.ParseFile(fset, name, nil, parser.SkipObjectResolution)
		if err != nil {
			return nil, errf(CodeLoadFailed, "cannot parse "+f+": "+err.Error())
		}
		ff := FileFuncs{File: strings.ReplaceAll(f, "\\", "/"), Package: file.Name.Name, Functions: []FuncInfo{}}
		for _, d := range file.Decls {
			fd, ok := d.(*ast.FuncDecl)
			if !ok {
				continue
			}
			ff.Functions = append(ff.Functions, FuncInfo{
				Symbol: declSymbol(fd), Start: fset.Position(fd.Pos()).Line, End: fset.Position(fd.End()).Line,
			})
		}
		out = append(out, ff)
	}
	return out, nil
}

// declSymbol is the vulndb symbol of a declaration: "Func" or "Type.Method" (no pointer, no type parameters).
func declSymbol(fd *ast.FuncDecl) string {
	if fd.Recv == nil || len(fd.Recv.List) == 0 {
		return fd.Name.Name
	}
	return recvTypeName(fd.Recv.List[0].Type) + "." + fd.Name.Name
}

func recvTypeName(e ast.Expr) string {
	for {
		switch t := e.(type) {
		case *ast.StarExpr:
			e = t.X
		case *ast.ParenExpr:
			e = t.X
		case *ast.IndexExpr:
			e = t.X
		case *ast.IndexListExpr:
			e = t.X
		case *ast.Ident:
			return t.Name
		default:
			return "?"
		}
	}
}
