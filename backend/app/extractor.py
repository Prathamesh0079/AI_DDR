import fitz
import os
import base64
import logging
import time
import hashlib
from PIL import Image
import io

logger = logging.getLogger(__name__)

IMAGE_DIR = "outputs/images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# ─── Filter thresholds (tuned per source type) ───
# Inspection PDFs: large high-res photos with lots of small icons
INSPECTION_FILTERS = {
    "min_width": 250,
    "min_height": 250,
    "min_raw_bytes": 15000,
    "max_aspect": 3.0,
    "max_per_page": 6,
}

# Thermal PDFs: smaller thermal scan images, often paired (visual + thermal)
# These are typically lower resolution but highly valuable diagnostically
THERMAL_FILTERS = {
    "min_width": 80,        # Support low-res thermal sensors (e.g. 80x60)
    "min_height": 60,
    "min_raw_bytes": 500,   # Thermal images can be very small
    "max_aspect": 4.0,      # Allow slightly wider panoramas
    "max_per_page": 100,    # Capture ALL thermal scans even in dense reports
}

# Compression settings
MAX_DIMENSION = 512
JPEG_QUALITY = 55


def _is_meaningful_image(width, height, raw_size, filters):
    """
    Filter out decorative elements: logos, icons, banners, page headers.
    Only keep images that are likely real inspection/thermal photos.
    """
    if width < filters["min_width"] or height < filters["min_height"]:
        return False
    if raw_size < filters["min_raw_bytes"]:
        return False
    # Skip very wide/thin banners
    aspect = max(width, height) / max(min(width, height), 1)
    if aspect > filters["max_aspect"]:
        return False
    return True


def _image_hash(pil_img):
    """
    Generate a 'visual hash' for deduplication.
    Identifies images that are visually identical even if their binary 
    encoding in the PDF differs.
    """
    try:
        # Resize to a small grayscale thumbnail to normalize
        thumb = pil_img.convert("L").resize((64, 64), Image.Resampling.LANCZOS)
        return hashlib.md5(thumb.tobytes()).hexdigest()
    except Exception as e:
        logger.warning(f"   ⚠️ Visual hashing failed: {e}")
        # Fallback to a random hash if this fails to avoid crashing
        return str(time.time())


def extract_pdf(file_path, prefix):
    """
    Extract text and images from a PDF file.
    Uses source-aware filtering: looser thresholds for thermal reports
    to capture more diagnostic images.
    """
    start_time = time.time()
    logger.info(f"📄 Starting PDF extraction: {file_path} (prefix: {prefix})")

    # Select filter profile based on source type
    is_thermal = prefix.lower() in ("thermal", "thermo", "ir", "infrared")
    filters = THERMAL_FILTERS if is_thermal else INSPECTION_FILTERS
    filter_name = "THERMAL (relaxed)" if is_thermal else "INSPECTION (standard)"
    logger.info(f"   Using {filter_name} image filters")
    logger.info(f"   Min size: {filters['min_width']}x{filters['min_height']}, "
                f"min bytes: {filters['min_raw_bytes']}, "
                f"max per page: {filters['max_per_page']}")

    doc = fitz.open(file_path)
    logger.info(f"   PDF has {len(doc)} pages")

    full_text = ""
    images = []
    total_raw = 0
    skipped_decorative = 0
    skipped_duplicate = 0
    skipped_per_page = 0

    seen_hashes = set()

    for page_num, page in enumerate(doc):
        page_text = page.get_text()
        full_text += page_text

        page_images = page.get_images(full=True)
        total_raw += len(page_images)
        page_kept = 0

        for img_index, img in enumerate(page_images):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                raw_size = len(img_bytes)

                pil_img = Image.open(io.BytesIO(img_bytes))
                original_w, original_h = pil_img.size

                # Filter out non-meaningful images using source-aware thresholds
                if not _is_meaningful_image(original_w, original_h, raw_size, filters):
                    if is_thermal and skipped_decorative < 20:
                        aspect = max(original_w, original_h) / max(min(original_w, original_h), 1)
                        logger.debug(f"   [DEBUG Thermal Skip] {original_w}x{original_h}, {raw_size} bytes, aspect {aspect:.2f}")
                    skipped_decorative += 1
                    continue

                # Deduplicate — skip images we've already seen
                img_hash = _image_hash(pil_img)
                if img_hash in seen_hashes:
                    skipped_duplicate += 1
                    continue
                seen_hashes.add(img_hash)

                # Limit images per page
                if page_kept >= filters["max_per_page"]:
                    skipped_per_page += 1
                    continue

                # Resize if too large
                if max(pil_img.size) > MAX_DIMENSION:
                    pil_img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)

                # Convert to RGB if necessary
                if pil_img.mode in ("RGBA", "P", "LA"):
                    pil_img = pil_img.convert("RGB")

                # Save as compressed JPEG
                img_io = io.BytesIO()
                pil_img.save(img_io, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                compressed_bytes = img_io.getvalue()
                compressed_kb = len(compressed_bytes) // 1024

                img_filename = f"{prefix}_page{page_num + 1}_img{img_index + 1}.jpg"
                img_path = f"{IMAGE_DIR}/{img_filename}"

                with open(img_path, "wb") as f:
                    f.write(compressed_bytes)

                img_b64 = base64.b64encode(compressed_bytes).decode("utf-8")

                logger.info(
                    f"   ✅ {img_filename}: {original_w}x{original_h} → "
                    f"{pil_img.size[0]}x{pil_img.size[1]}, {compressed_kb}KB"
                )

                # Extract surrounding text context for the LLM
                context_snippet = page_text.strip()[:500] if page_text.strip() else "No text context on this page"

                images.append({
                    "path": img_path,
                    "filename": img_filename,
                    "page": page_num + 1,
                    "base64": img_b64,
                    "mime_type": "image/jpeg",
                    "context": context_snippet,
                    "source": prefix
                })
                page_kept += 1

            except Exception as e:
                logger.warning(f"   ⚠️ Failed to process image {img_index} on page {page_num + 1}: {e}")
                continue

    doc.close()

    elapsed = time.time() - start_time
    total_payload_kb = sum(len(img["base64"]) for img in images) // 1024

    logger.info(f"{'=' * 50}")
    logger.info(
        f"✅ Extraction done: {prefix} | {elapsed:.2f}s\n"
        f"   Text: {len(full_text)} chars\n"
        f"   Images: {len(images)} kept / {total_raw} total\n"
        f"   Skipped: {skipped_decorative} decorative, {skipped_duplicate} duplicate, "
        f"{skipped_per_page} per-page limit\n"
        f"   Payload: ~{total_payload_kb}KB of base64 image data"
    )
    logger.info(f"{'=' * 50}")

    return full_text, images