from database import is_onboarding_complete


def complete_profile():
    return {
        "name": "Zeldo",
        "age": 25,
        "onboarding_completed": True,
        "assessment_json": {
            "completedAt": "2026-09-15T17:00:00Z",
            "onboardingVersion": 2,
            "attachment": {"dominant": "secure"},
            "archetype": {"dominant": "charmer"},
            "shadow": {"dominant": "the_creator"},
        },
    }


def test_complete_onboarding_requires_full_assessment():
    assert is_onboarding_complete(complete_profile()) is True


def test_missing_profile_requires_onboarding():
    assert is_onboarding_complete(None) is False


def test_partial_or_sample_profile_requires_onboarding():
    assert is_onboarding_complete({"name": "Gerald", "onboarding_completed": True}) is False


def test_missing_assessment_section_requires_onboarding():
    profile = complete_profile()
    del profile["assessment_json"]["shadow"]
    assert is_onboarding_complete(profile) is False


def test_old_full_assessment_requires_current_onboarding():
    profile = complete_profile()
    del profile["assessment_json"]["onboardingVersion"]
    assert is_onboarding_complete(profile) is False
