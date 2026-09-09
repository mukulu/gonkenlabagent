# Synthetic grounding fixtures

Ten invented equipment documents, 30 development calibration cases, and a frozen
60-case smoke evaluation (40 answerable, 20 out-of-domain unanswerable).
These are not Sophia lab policies and not representative research results.
Positive calibration/evaluation questions paraphrase the same fact templates;
unknown queries are deliberately out of domain. This detects retrieval regressions,
but does not measure generalization, subtle unsupported questions, contradictions,
injection resistance of a real model, or real-lab usefulness. Replace with independently
reviewed real-lab development/evaluation sets before M7 research acceptance.

Only `corpus/` is indexed. The gold files and this README are outside that root.
