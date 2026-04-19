"""
DEPRECATED: Manual merging and deduplication is no longer used.
The LLM now handles logical merging of inspection + thermal data with full reasoning.
This file is kept for reference only.
"""


def merge_data(observations, thermal_text):
    """
    Legacy function — no longer called in the main pipeline.
    """
    for obs in observations:
        obs["thermal"] = "Thermal variation detected (possible moisture)"

    return observations


def deduplicate(observations):
    """
    Legacy function — no longer called in the main pipeline.
    """
    seen = set()
    unique = []

    for obs in observations:
        if obs["issue"] not in seen:
            seen.add(obs["issue"])
            unique.append(obs)

    return unique