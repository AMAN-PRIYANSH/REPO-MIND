import pytest

from vulntrace.dataset.govers import InvalidVersion, parse_version, pseudo_version_commit, smallest_fixed_above


def test_plain_version():
    v = parse_version("0.159.1")
    assert (v.major, v.minor, v.patch) == (0, 159, 1)
    assert str(v) == "v0.159.1"


def test_v_prefix_accepted():
    assert parse_version("v0.159.1") == parse_version("0.159.1")


def test_incompatible_suffix():
    v = parse_version("3.2.0+incompatible")
    assert v.incompatible and str(v) == "v3.2.0+incompatible"


def test_prerelease_ordering():
    assert parse_version("1.0.0-alpha") < parse_version("1.0.0")
    assert parse_version("1.0.0-alpha") < parse_version("1.0.0-alpha.1")
    assert parse_version("1.0.0-alpha.1") < parse_version("1.0.0-alpha.beta")
    assert parse_version("1.0.0-rc.2") < parse_version("1.0.0-rc.10")  # numeric, not lexical


def test_release_ordering():
    assert parse_version("0.159.1") < parse_version("0.159.2") < parse_version("0.160.0") < parse_version("1.0.0")


def test_equal_ignores_build_metadata():
    assert parse_version("1.2.3+incompatible") == parse_version("1.2.3")


@pytest.mark.parametrize("bad", ["", "not-a-version", "1.07", "0.9.1.3", "latest", "RELEASE.2024-06-06T09-36-42Z",
                                 "edge-24.6.2", "main-gha.27122"])
def test_invalid_versions_rejected(bad):
    """These forms were observed in the real vulndb corpus (non-semver tags, e.g. MinIO's
    RELEASE.* scheme, and a few malformed/legacy version strings)."""
    with pytest.raises(InvalidVersion):
        parse_version(bad)


@pytest.mark.parametrize("v,commit", [
    ("0.0.0-20160722212129-ac0cc4484ad4", "ac0cc4484ad4"),  # no base version
    ("1.4.3-0.20191129212618-4f2e80285f2e", "4f2e80285f2e"),  # building on a release
    ("4.0.0-20190408202314-32acca36b99f", "32acca36b99f"),
    ("0.0.0-20160722212129-ac0cc4484ad4+incompatible", "ac0cc4484ad4"),
])
def test_pseudo_version_commit_extracted(v, commit):
    assert pseudo_version_commit(v) == commit


@pytest.mark.parametrize("v", ["0.159.1", "3.2.0+incompatible", "1.0.0-alpha"])
def test_non_pseudo_versions_have_no_commit(v):
    assert pseudo_version_commit(v) is None


def test_pseudo_version_with_nonstandard_hash_length_still_resolves():
    """Real golang/vulndb reports contain hand-edited pseudo-versions whose abbreviated
    commit hash is not exactly the spec's 12 hex digits (11, 13 and 14 were observed)."""
    assert pseudo_version_commit("0.7.1-0.20250129155113-4c6e03c463141") == "4c6e03c463141"  # 13 chars
    assert pseudo_version_commit("1.9.10-0.20251005005631-6de168c9454") == "6de168c9454"  # 11 chars


def test_pseudo_version_missing_commit_hash_is_unresolved():
    """A handful of real reports have a timestamp with no trailing commit hash at all; this
    genuinely cannot be resolved (feeds PSEUDO_VERSION_UNRESOLVED in the release-range step)."""
    assert pseudo_version_commit("0.0.0-20220724015452") is None


def test_smallest_fixed_above_picks_the_minimum_strictly_greater_version():
    assert smallest_fixed_above("0.159.1", ["0.160.0", "0.159.2", "0.159.1"]) == "0.159.2"


def test_smallest_fixed_above_returns_none_when_nothing_is_greater():
    assert smallest_fixed_above("1.0.0", ["0.9.0", "1.0.0"]) is None


def test_smallest_fixed_above_skips_unparseable_candidates():
    assert smallest_fixed_above("1.0.0", ["not-a-version", "1.1.0"]) == "1.1.0"


def test_smallest_fixed_above_unparseable_base_returns_none():
    assert smallest_fixed_above("not-a-version", ["1.1.0"]) is None


def test_determinism():
    assert parse_version("0.0.0-20160722212129-ac0cc4484ad4+incompatible") == \
        parse_version("0.0.0-20160722212129-ac0cc4484ad4+incompatible")
