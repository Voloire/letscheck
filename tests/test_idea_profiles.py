from astrochecker.idea_profiles import IDEA_MIN_BLOCK_SECONDS, classify_candidate


def record(object_type="OCl", name="NGC 123", **extra):
    return {
        "name": name,
        "type": object_type,
        "ra_deg": 10.0,
        "dec_deg": 20.0,
        "aliases": [name],
        **extra,
    }


def test_clusters_are_eligible_and_beginner_messier_objects_get_a_boost():
    profile = classify_candidate(record("GCl", "NGC 6205", aliases=["NGC 6205", "M 13"]))

    assert profile["eligible"] is True
    assert profile["category"] == "cluster"
    assert profile["beginner"] is True
    assert profile["priority"] > classify_candidate(record("GCl", "NGC 9999"))["priority"]
    assert profile["minimum_block_seconds"] == IDEA_MIN_BLOCK_SECONDS == 7200


def test_emission_and_reflection_nebulae_have_highest_priority():
    emission = classify_candidate(record("EmN", "Sh 2-999"))
    reflection = classify_candidate(record("RfN", "vdB 999"))
    cluster = classify_candidate(record("OCl", "NGC 6940"))

    assert emission["eligible"] and reflection["eligible"]
    assert emission["priority"] == reflection["priority"]
    assert emission["priority"] > cluster["priority"]


def test_compact_galaxies_are_eligible_but_extended_galaxies_are_excluded():
    compact = classify_candidate(record("G", "NGC 224", major_axis_arcmin=12))
    extended = classify_candidate(record("G", "NGC 999", major_axis_arcmin=45))

    assert compact["eligible"] is True
    assert compact["category"] == "galaxy"
    assert extended["eligible"] is False
    assert "estesa" in extended["reason"].lower()


def test_galaxy_without_angular_size_is_excluded_from_automatic_ideas():
    profile = classify_candidate(record("G", "NGC 9999"))

    assert profile["eligible"] is False
    assert "dimension" in profile["reason"].lower()


def test_stellar_unknown_duplicate_and_incomplete_records_are_excluded_with_reasons():
    profiles = [
        classify_candidate(record("**", "HD 1")),
        classify_candidate(record("mystery", "X 1")),
        classify_candidate(record("OCl", "NGC 2", duplicate=True)),
        classify_candidate({"name": "NGC 3", "type": "OCl", "ra_deg": None, "dec_deg": 1}),
    ]

    assert all(profile["eligible"] is False for profile in profiles)
    assert all(profile["reason"] for profile in profiles)
