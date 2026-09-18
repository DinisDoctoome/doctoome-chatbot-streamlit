import pytest

from localization import feedback_reason_options, translate


@pytest.mark.parametrize(
    "language,key,expected",
    [
        ("en", "suggestion_title", "Have a suggestion?"),
        ("fr", "suggestion_title", "Une suggestion ?"),
        ("en", "feedback_question", "What went wrong?"),
        ("fr", "feedback_question", "Qu'est-ce qui n'a pas fonctionné ?"),
    ],
)
def test_frontend_strings_are_translated(language, key, expected):
    assert translate(language, key) == expected


def test_feedback_reason_values_are_stable_across_languages():
    english = feedback_reason_options("en")
    french = feedback_reason_options("fr")

    assert list(english) == list(french) == [
        "misunderstood_request",
        "wrong_result",
        "missing_feature_or_filter",
        "too_many_questions",
        "technical_problem",
        "other",
    ]
    assert english["technical_problem"] == "Technical problem"
    assert french["technical_problem"] == "Problème technique"
