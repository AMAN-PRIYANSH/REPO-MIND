"""End-to-end triage (CP7): advisory -> target symbols -> two reachability methods per symbol and
main package -> rule table (`vulntrace.verdict`) -> evidence verifier -> case verdict -> policy.

Reachability only, never exploitability. No LLM and no agent is used anywhere on this path
(CP5 E1 and CP6 findings): Mode 1 checks every changed non-test function of the fix, Mode 2
checks the fixed retriever's top-k candidates.
"""
