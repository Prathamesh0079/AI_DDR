"""
DEPRECATED: Manual text parsing is no longer used.
The LLM now handles extraction, reasoning, and structuring directly from raw text.
This file is kept for reference only.
"""


def extract_observations(text):
    """
    Legacy function — no longer called in the main pipeline.
    The LLM processor now handles observation extraction with full context.
    """
    observations = []

    lines = text.split("\n")

    for line in lines:
        if "Observed" in line:
            observations.append({
                "issue": line.strip(),
                "source": "inspection"
            })

    return observations