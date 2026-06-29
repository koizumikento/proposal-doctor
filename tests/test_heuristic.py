from proposal_doctor.heuristic import review_with_heuristics
from proposal_doctor.lenses import DEFAULT_LENSES


def test_execution_risk_lens_flags_missing_delivery_plan() -> None:
    lens = next(lens for lens in DEFAULT_LENSES if lens.name == "execution_risk")

    review = review_with_heuristics(
        "We can improve conversion and reduce support load.",
        "enterprise buyer",
        lens,
    )

    assert review.findings
    assert review.findings[0].severity == "high"
