from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import json
import base64
import logging
import time
import re
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log
)

logger = logging.getLogger(__name__)

# ✅ Load .env file
load_dotenv()

# ✅ Get API key
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not found. Please check your .env file")

client = genai.Client(api_key=api_key)

MODEL = "gemini-2.5-flash"


def clean_json(text):
    """
    Clean Gemini response — remove markdown fences, extract JSON object,
    and attempt to repair common LLM JSON errors (trailing commas, 
    unescaped control characters, truncated output).
    """
    text = text.strip()

    # Remove markdown code fences
    if "```" in text:
        text = text.replace("```json", "").replace("```", "")

    # Extract JSON object
    start = text.find("{")
    end = text.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No valid JSON object found in LLM response")

    json_str = text[start:end]

    # Try parsing as-is first
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        logger.warning("⚠️ Raw JSON parse failed, attempting auto-repair...")

    # --- Repair Strategies ---
    
    # 1. Remove trailing commas before } or ]
    repaired = re.sub(r',\s*([}\]])', r'\1', json_str)
    
    # 2. Fix unescaped control characters (newlines, tabs in strings)
    # This is a common cause for "Expecting ',' delimiter" errors
    def fix_control_chars(match):
        s = match.group(0)
        # Escape actual newlines/tabs inside strings
        return s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    
    repaired = re.sub(r'"[^"\\\\]*(?:\\\\.[^"\\\\]*)*"', fix_control_chars, repaired)

    try:
        json.loads(repaired)
        logger.info("✅ JSON auto-repair (Strategy 1 & 2) successful")
        return repaired
    except json.JSONDecodeError:
        pass

    # 3. Handle Truncation (if the response ended prematurely)
    # Count open braces/brackets and try to close them
    open_braces = repaired.count('{') - repaired.count('}')
    open_brackets = repaired.count('[') - repaired.count(']')
    
    if open_braces > 0 or open_brackets > 0:
        logger.warning(f"⚠️ Detected possible truncated JSON (Braces: {open_braces}, Brackets: {open_brackets})")
        
        # Trim to the last complete item if it ends in a comma or a partial field
        # This is a bit aggressive but often works
        if repaired.strip().endswith(','):
            repaired = repaired.strip()[:-1]
        
        repaired += ']' * open_brackets
        repaired += '}' * open_braces
        
        try:
            json.loads(repaired)
            logger.info("✅ Truncated JSON successfully closed and repaired")
            return repaired
        except json.JSONDecodeError:
            pass

    # If all repairs fail, return the original json_str and let the calling 
    # function handle the last parse attempt which will log the error details.
    return json_str


def _build_image_catalog(images):
    """
    Build a text catalog describing all extracted images for the LLM.
    """
    catalog_lines = []
    for img in images:
        catalog_lines.append(
            f"- Image ID: \"{img['filename']}\" | Source: {img['source']} report | "
            f"Page: {img['page']} | Page context: \"{img['context'][:200]}...\""
        )
    return "\n".join(catalog_lines)


def _build_multimodal_parts(images):
    """
    Build multimodal content parts for Gemini from extracted images.
    Include images as inline data for vision analysis.
    """
    parts = []
    for img in images:
        try:
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(img["base64"]),
                    mime_type=img["mime_type"]
                )
            )
            parts.append(
                types.Part.from_text(
                    text=f"[Above image is: {img['filename']} from {img['source']} report, page {img['page']}]"
                )
            )
        except Exception as e:
            logger.warning(f"⚠️ Skipping image {img.get('filename', '?')}: {e}")
            continue

    logger.info(f"   Built {len(parts) // 2} image parts for multimodal input")
    return parts


def _is_transient_error(exception):
    """Check if the exception is a transient 503 or 500 error from Gemini."""
    from google.genai.errors import ServerError
    if isinstance(exception, ServerError):
        # 503 is Service Unavailable (high demand), 500 is Internal Server Error
        # In google-genai, the attribute is 'code'
        code = getattr(exception, "code", None)
        return code in [500, 503, 504, 429]
    return False


@retry(
    retry=retry_if_exception(_is_transient_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def _generate_content_with_retry(content_parts):
    """Helper to call Gemini API with exponential backoff on transient errors."""
    return client.models.generate_content(
        model=MODEL,
        contents=content_parts,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=65536,  # Large limit to avoid truncation
            http_options={"timeout": 300_000},  # 5 minute timeout for Gemini API
        )
    )


def generate_ddr(inspection_text, thermal_text, images):
    """
    Generate a Detailed Diagnostic Report using Gemini with multimodal input.
    """
    try:
        total_start = time.time()

        logger.info("=" * 60)
        logger.info("🤖 Starting DDR generation with Gemini")
        logger.info(f"   Model: {MODEL}")
        logger.info(f"   Inspection text: {len(inspection_text)} chars")
        logger.info(f"   Thermal text: {len(thermal_text)} chars")
        logger.info(f"   Images: {len(images)}")
        logger.info("=" * 60)

        # Build image catalog
        image_catalog = _build_image_catalog(images)
        logger.info(f"📋 Image catalog built ({len(images)} entries)")

        prompt = f"""You are a senior building inspection expert preparing a professional Detailed Diagnostic Report (DDR) for a client.

TASK:
Analyze the provided Inspection Report text and Thermal Report text. Also review the attached images extracted from these reports. 
Generate a comprehensive, client-ready DDR.

STRICT RULES:
1. Do NOT invent or assume facts not present in the documents
2. If information is missing → write "Not Available"
3. If information conflicts between reports → explicitly mention the conflict
4. Use simple, client-friendly language — avoid unnecessary technical jargon
5. Severity must be one of: Low, Moderate, High, Critical
6. For each area-wise observation, assign the most relevant image(s) from the catalog below
7. If no relevant image exists for an observation, set image to "Image Not Available"
8. Extract site/property metadata from the documents wherever available
9. For each image you assign, provide a short descriptive caption explaining what it shows
10. IMPORTANT — MAXIMIZE THERMAL EVIDENCE: Use EVERY relevant thermal image from the catalog. Each observation should ideally have multiple thermal scans (prefixed with "thermal_") to show different angles or details of the issue. Use them to back up every technical claim you make.
11. VARIETY & UNIQUENESS: Do NOT repeat the same image for multiple observations. Each unique image filename from the catalog should be assigned ONLY ONCE in the entire report if possible. We want the client to see new proof for every finding, not the same few photos over and over.
12. If a thermal scan corresponds to a regular photo, include BOTH in the observation.
13. If you have 30 unique thermal images, use as many as possible across the observations to provide a "thick" report with rich evidence.

IMAGE CATALOG (images extracted from the reports):
{image_catalog}

OUTPUT FORMAT — Return ONLY valid JSON matching this exact structure:

{{
  "SiteMetadata": {{
    "ClientName": "Name of the client or flat/unit owner (extract from report header or text)",
    "SiteAddress": "Full address of the property being inspected",
    "TypeOfStructure": "e.g., Flat, Row House, Apartment, Bungalow",
    "Floors": "Number of floors",
    "YearOfConstruction": "Year or approximate period",
    "AgeOfBuilding": "Age in years if mentioned",
    "DateOfInspection": "Date when inspection was conducted",
    "InspectedBy": "Name of inspector if mentioned",
    "PreparedFor": "Who the report is prepared for"
  }},
  "PropertyIssueSummary": "A clear 2-3 sentence summary of overall property issues found",
  "AreaWiseObservations": [
    {{
      "area": "Name of the area (e.g., Master Bedroom, Bathroom, Balcony, Terrace)",
      "issue": "Clear description of the observed issue",
      "severity": "Low | Moderate | High | Critical",
      "reasoning": "Why this severity was assigned, based on evidence from both reports",
      "images": ["filename1.png", "filename2.png"],
      "image_captions": ["Description of what image 1 shows", "Description of what image 2 shows"],
      "thermal_finding": "Related thermal finding if available, otherwise Not Available"
    }}
  ],
  "ImpactSummaryTable": [
    {{
      "impacted_area": "The area showing damage/symptoms (negative side, e.g., Ceiling dampness in Hall)",
      "source_area": "The source/root of the problem (positive side, e.g., Gaps in bathroom tile joints above)"
    }}
  ],
  "ProbableRootCause": "Overall analysis of probable root causes based on both reports",
  "SeverityAssessment": "Overall severity assessment with reasoning based on combined findings",
  "RecommendedActions": [
    "Specific, actionable recommendation 1",
    "Specific, actionable recommendation 2"
  ],
  "AdditionalNotes": "Any additional observations, caveats, or notes for the client",
  "MissingOrUnclearInformation": [
    "Specific item that was missing or unclear in the source documents"
  ]
}}

=== INSPECTION REPORT TEXT ===
{inspection_text}

=== THERMAL REPORT TEXT ===
{thermal_text}

Remember: Return ONLY the JSON object, no other text.
"""

        # Build multimodal content: images first, then the text prompt
        logger.info("🖼️ Building multimodal parts...")
        parts_start = time.time()
        content_parts = _build_multimodal_parts(images)
        content_parts.append(types.Part.from_text(text=prompt))
        logger.info(f"   Multimodal parts built in {time.time() - parts_start:.2f}s")

        # Calculate approximate payload size
        total_b64_size = sum(len(img.get("base64", "")) for img in images)
        logger.info(f"   Approximate payload size: {total_b64_size // 1024}KB of image data")

        logger.info("📡 Sending request to Gemini API (with retry support)...")
        api_start = time.time()

        response = _generate_content_with_retry(content_parts)

        api_elapsed = time.time() - api_start
        logger.info(f"✅ Gemini API responded in {api_elapsed:.2f}s")

        # Check finish reason for truncation
        finish_reason = None
        if response.candidates and len(response.candidates) > 0:
            finish_reason = response.candidates[0].finish_reason
            logger.info(f"   Finish reason: {finish_reason}")
            if str(finish_reason) == 'MAX_TOKENS' or str(finish_reason) == '2':
                logger.warning("⚠️ Response was TRUNCATED by token limit!")

        raw_text = response.text
        logger.info(f"   Response length: {len(raw_text)} chars")
        logger.info(f"   Response ends with: ...{raw_text[-100:]}")

        # Clean and parse JSON
        logger.info("🔧 Parsing JSON response...")
        cleaned = clean_json(raw_text)
        result = json.loads(cleaned)

        # Validate required fields exist
        required_fields = [
            "PropertyIssueSummary", "AreaWiseObservations", "ProbableRootCause",
            "SeverityAssessment", "RecommendedActions", "AdditionalNotes",
            "MissingOrUnclearInformation"
        ]
        missing_fields = []
        for field in required_fields:
            if field not in result:
                result[field] = "Not Available" if field != "AreaWiseObservations" else []
                missing_fields.append(field)

        if missing_fields:
            logger.warning(f"⚠️ Missing fields filled with defaults: {missing_fields}")

        # Log what we actually got for each field
        obs_count = len(result.get("AreaWiseObservations", [])) if isinstance(result.get("AreaWiseObservations"), list) else 0
        total_elapsed = time.time() - total_start

        logger.info("=" * 60)
        logger.info(f"🎉 DDR generation complete!")
        logger.info(f"   PropertyIssueSummary: {len(str(result.get('PropertyIssueSummary', '')))} chars")
        logger.info(f"   AreaWiseObservations: {obs_count} items")
        logger.info(f"   ProbableRootCause: {len(str(result.get('ProbableRootCause', '')))} chars")
        logger.info(f"   SeverityAssessment: {len(str(result.get('SeverityAssessment', '')))} chars")
        actions = result.get('RecommendedActions', [])
        logger.info(f"   RecommendedActions: {len(actions) if isinstance(actions, list) else 'string: ' + str(len(str(actions))) + ' chars'}")
        logger.info(f"   AdditionalNotes: {len(str(result.get('AdditionalNotes', '')))} chars")
        missing_info = result.get('MissingOrUnclearInformation', [])
        logger.info(f"   MissingOrUnclearInformation: {len(missing_info) if isinstance(missing_info, list) else 'string: ' + str(len(str(missing_info))) + ' chars'}")
        logger.info(f"   Total time: {total_elapsed:.2f}s (API: {api_elapsed:.2f}s)")
        logger.info("=" * 60)

        return result

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}")
        logger.error(f"   Raw response (first 500 chars): {raw_text[:500] if 'raw_text' in locals() else 'N/A'}")
        return {
            "error": f"Failed to parse LLM response as JSON: {str(e)}",
            "raw_response": raw_text if "raw_text" in locals() else "No response"
        }
    except Exception as e:
        logger.error(f"❌ DDR generation failed: {e}", exc_info=True)
        return {
            "error": f"Failed to generate report: {str(e)}",
            "raw_response": raw_text if "raw_text" in locals() else "No response"
        }