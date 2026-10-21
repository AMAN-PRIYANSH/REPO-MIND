"""Pure tag-naming logic for CP3 deliverable 4 (no git, no network)."""

from vulntrace.dataset.release_range import candidate_tags, module_subdir, split_major_suffix, strip_incompatible


def test_strip_incompatible():
    assert strip_incompatible("3.2.0+incompatible") == "3.2.0"
    assert strip_incompatible("3.2.0") == "3.2.0"


def test_split_major_suffix_v2_plus():
    assert split_major_suffix("github.com/x/y/v3") == ("github.com/x/y", 3)
    assert split_major_suffix("github.com/x/y/v2") == ("github.com/x/y", 2)


def test_split_major_suffix_v0_v1_have_no_suffix():
    assert split_major_suffix("github.com/x/y") == ("github.com/x/y", None)
    assert split_major_suffix("github.com/x/y/v1") == ("github.com/x/y/v1", None)  # v1 is not a path suffix
    assert split_major_suffix("github.com/x/y/v0") == ("github.com/x/y/v0", None)


def test_split_major_suffix_does_not_mistake_a_version_looking_directory():
    """A directory literally named "v3" is a real possible path component (e.g. a client
    SDK "v3" subdir without that being a go module major-version suffix at all) - this
    function cannot tell the difference from the path alone, a documented limitation; it
    always treats a trailing "/vN" (N>=2) as a major-version suffix."""
    assert split_major_suffix("github.com/x/y/v3") == ("github.com/x/y", 3)


def test_module_subdir_matches_repo_root():
    assert module_subdir("github.com/o/r", "o", "r") == ""


def test_module_subdir_matches_a_real_subdirectory():
    assert module_subdir("github.com/o/r/sub/dir", "o", "r") == "sub/dir"


def test_module_subdir_strips_major_version_suffix_before_matching():
    assert module_subdir("github.com/o/r/v3", "o", "r") == ""
    assert module_subdir("github.com/o/r/sub/v2", "o", "r") == "sub"


def test_module_subdir_falls_back_to_root_for_a_vanity_import():
    """goa.design/goa/v3's actual code lives in github.com/goadesign/goa (per the fix
    commit); the module path itself gives no way to recover the subdirectory, so this
    documented limitation assumes the repo root."""
    assert module_subdir("goa.design/goa/v3", "goadesign", "goa") == ""


def test_candidate_tags_root_module():
    assert candidate_tags("github.com/o/r", "1.2.3", "o", "r") == ["v1.2.3"]


def test_candidate_tags_submodule_uses_subdir_prefix_only():
    assert candidate_tags("github.com/o/r/sub", "1.2.3", "o", "r") == ["sub/v1.2.3"]


def test_candidate_tags_major_version_tries_root_then_subdirectory_convention():
    assert candidate_tags("github.com/o/r/v3", "3.0.1", "o", "r") == ["v3.0.1", "v3/v3.0.1"]


def test_candidate_tags_strips_incompatible_suffix():
    assert candidate_tags("github.com/o/r", "3.2.0+incompatible", "o", "r") == ["v3.2.0"]
