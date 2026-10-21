from vulntrace.dataset.diffparse import new_range, old_range, overlaps_function, parse_hunks

SINGLE_HUNK_DIFF = """diff --git a/lib.go b/lib.go
index 1111111..2222222 100644
--- a/lib.go
+++ b/lib.go
@@ -3,2 +3,3 @@ func Vuln(s string) string {
-\treturn s
+\treturn sanitize(s)
+// comment
"""

TWO_HUNK_DIFF = """diff --git a/lib.go b/lib.go
index 1111111..2222222 100644
--- a/lib.go
+++ b/lib.go
@@ -3 +3,2 @@ func Vuln(s string) string {
+\t// note
@@ -10,3 +11,3 @@ func Other() {
-\told
+\tnew
 \tcontext
"""

PURE_INSERTION_DIFF = """diff --git a/lib.go b/lib.go
--- a/lib.go
+++ b/lib.go
@@ -5,0 +6,2 @@ func F() {
+\tline1
+\tline2
"""

PURE_DELETION_DIFF = """diff --git a/lib.go b/lib.go
--- a/lib.go
+++ b/lib.go
@@ -5,2 +4,0 @@ func F() {
-\tline1
-\tline2
"""


def test_single_hunk_parsed():
    hunks = parse_hunks(SINGLE_HUNK_DIFF)
    assert len(hunks) == 1
    h = hunks[0]
    assert (h["old_start"], h["old_lines"], h["new_start"], h["new_lines"]) == (3, 2, 3, 3)
    assert h["text"] == "-\treturn s\n+\treturn sanitize(s)\n+// comment"


def test_multiple_hunks_parsed_in_order():
    hunks = parse_hunks(TWO_HUNK_DIFF)
    assert len(hunks) == 2
    assert (hunks[0]["old_start"], hunks[0]["old_lines"]) == (3, 1)  # omitted count defaults to 1
    assert (hunks[0]["new_start"], hunks[0]["new_lines"]) == (3, 2)
    assert (hunks[1]["old_start"], hunks[1]["old_lines"], hunks[1]["new_start"], hunks[1]["new_lines"]) == (10, 3, 11, 3)
    assert hunks[1]["text"].splitlines() == ["-\told", "+\tnew", " \tcontext"]


def test_no_hunks_in_a_diff_with_no_changes():
    assert parse_hunks("") == []


def test_old_range_and_new_range():
    h = parse_hunks(SINGLE_HUNK_DIFF)[0]
    assert old_range(h) == (3, 4)
    assert new_range(h) == (3, 5)


def test_pure_insertion_has_no_old_range():
    h = parse_hunks(PURE_INSERTION_DIFF)[0]
    assert old_range(h) is None
    assert new_range(h) == (6, 7)


def test_pure_deletion_has_no_new_range():
    h = parse_hunks(PURE_DELETION_DIFF)[0]
    assert old_range(h) == (5, 6)
    assert new_range(h) is None


def test_overlaps_function_with_a_real_range():
    assert overlaps_function((3, 4), 3, func_start=1, func_end=10)
    assert not overlaps_function((3, 4), 3, func_start=20, func_end=30)
    assert overlaps_function((3, 4), 3, func_start=4, func_end=4)  # touches the function's last line


def test_overlaps_function_for_a_pure_insertion_uses_the_insertion_point():
    # Inserted lines land just before line 6: counts for the function spanning [1,10]...
    assert overlaps_function(None, 6, func_start=1, func_end=10)
    # ...and for a function ending exactly at line 5 (insertion right after it)...
    assert overlaps_function(None, 6, func_start=1, func_end=5)
    # ...but not for a function that ends well before the insertion point.
    assert not overlaps_function(None, 6, func_start=1, func_end=3)
