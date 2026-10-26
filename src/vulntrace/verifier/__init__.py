"""Evidence verifier (C6, CP7; contract: INTERFACES_AND_CONTRACTS.md section 6).

It re-checks a verdict's evidence against the analysed source and the call graph and can only
weaken results: a failed check turns the affected entry into CANT_DETERMINE with
VERIFIER_REJECTED. It never upgrades a result, never adds a symbol and never edits a path; a
REACHABLE result keeps one of the method's own paths, unchanged, as `verified_path`.
"""
