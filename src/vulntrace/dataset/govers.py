"""Go module version parsing and comparison (CP3 D2/D4).

vulndb reports write versions without the leading "v" (e.g. "0.159.1", not
"v0.159.1"); this module accepts both. Comparison follows semver precedence
(https://semver.org): build metadata (`+incompatible`) is ignored for
ordering, and a pre-release version orders before its own release.
"""

import re
from dataclasses import dataclass
from functools import total_ordering

_VERSION = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)

# A pseudo-version's prerelease/base ends in "<14-digit timestamp>-<abbreviated commit>".
# Grammar (cmd/go/internal/modfetch/pseudo.go): vX.0.0-yyyymmddhhmmss-abcdefabcdef (no base),
# vX.Y.Z-pre.0.yyyymmddhhmmss-abcdefabcdef (on a pre-release), or
# vX.Y.(Z+1)-0.yyyymmddhhmmss-abcdefabcdef (on a release). The spec fixes the commit hash at
# 12 hex digits, but real golang/vulndb reports were observed to contain hand-edited pseudo-
# versions with other lengths (11 to 14 hex digits seen), so this accepts any length git
# itself would still treat as an unambiguous abbreviated hash (7-40).
_PSEUDO_SUFFIX = re.compile(r"(?:^|[.-])(\d{14})-([0-9a-fA-F]{7,40})$")


class InvalidVersion(ValueError):
    pass


@total_ordering
@dataclass(frozen=True, order=False, eq=False)
class GoVersion:
    """A parsed Go module version. Comparable; `str()` gives back a canonical "vX.Y.Z..." form."""

    major: int
    minor: int
    patch: int
    prerelease: str | None  # original dotted text, e.g. "0.20191129212618-4f2e80285f2e"; None if release
    build: str | None
    raw: str
    incompatible: bool

    def __str__(self) -> str:
        s = f"v{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += "-" + self.prerelease
        if self.incompatible:
            s += "+incompatible"
        return s

    @property
    def is_pseudo(self) -> bool:
        return pseudo_version_commit(self.raw) is not None

    def _sort_key(self):
        # Semver precedence: a pre-release sorts before the same release without one.
        pre = (0, _prerelease_key(self.prerelease)) if self.prerelease else (1,)
        return (self.major, self.minor, self.patch, pre)

    def __eq__(self, other):
        if not isinstance(other, GoVersion):
            return NotImplemented
        return self._sort_key() == other._sort_key()

    def __lt__(self, other):
        if not isinstance(other, GoVersion):
            return NotImplemented
        return self._sort_key() < other._sort_key()

    def __hash__(self):
        return hash(self._sort_key())


def _prerelease_key(s: str) -> tuple:
    """One dotted prerelease identifier, ordered the way semver orders prerelease fields:
    numeric identifiers compare numerically and sort before any alphanumeric identifier."""
    parts = []
    for ident in s.split("."):
        if ident.isdigit():
            parts.append((0, int(ident), ""))
        else:
            parts.append((1, 0, ident))
    return tuple(parts)


def parse_version(v: str) -> GoVersion:
    """Parse a version string as it appears in a vulndb report (with or without "v" prefix,
    with or without the "+incompatible" suffix, pseudo-versions included)."""
    s = v.strip()
    m = _VERSION.match(s)
    if not m:
        raise InvalidVersion(f"not a Go module version: {v!r}")
    return GoVersion(
        major=int(m.group("major")), minor=int(m.group("minor")), patch=int(m.group("patch")),
        prerelease=m.group("prerelease"), build=m.group("build"), raw=s,
        incompatible=m.group("build") == "incompatible",
    )


def pseudo_version_commit(v: str) -> str | None:
    """The 12-hex-digit abbreviated commit hash embedded in a pseudo-version, or None if `v`
    is not a pseudo-version. Verified against the examples in golang/vulndb reports, e.g.
    "0.0.0-20160722212129-ac0cc4484ad4" -> "ac0cc4484ad4"."""
    base = v.strip()
    if base.endswith("+incompatible"):
        base = base[: -len("+incompatible")]
    m = _PSEUDO_SUFFIX.search(base)
    return m.group(2) if m else None


def smallest_fixed_above(vulnerable_at: str, fixed_candidates: list[str]) -> str | None:
    """The smallest of `fixed_candidates` that is strictly greater than `vulnerable_at`
    (feasibility trial 5's rule), or None if there is no such candidate. Unparseable
    candidates are skipped (never raise): a report occasionally has a non-semver typo and
    the caller must still make progress on the rest of the corpus."""
    try:
        va = parse_version(vulnerable_at)
    except InvalidVersion:
        return None
    above = []
    for c in fixed_candidates:
        try:
            pv = parse_version(c)
        except InvalidVersion:
            continue
        if pv > va:
            above.append((pv, c))
    if not above:
        return None
    above.sort(key=lambda pair: pair[0])
    return above[0][1]
