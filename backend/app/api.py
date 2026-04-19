from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import shutil
import os
import logging
import time

from app.extractor import extract_pdf
from app.llm_processor import generate_ddr
from app.image_mapper import map_images_to_observations
from app.pdf_generator import generate_pdf

# ===== Logging Setup =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI DDR Generator",
    description="AI-powered Detailed Diagnostic Report generator from inspection and thermal PDFs",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/images", exist_ok=True)

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


@app.get("/")
def home():
    return {"message": "AI DDR Generator Backend Running 🚀", "version": "1.0.0"}


@app.post("/generate-report")
async def generate_report(
    inspection: UploadFile = File(..., description="Inspection Report PDF"),
    thermal: UploadFile = File(..., description="Thermal Report PDF")
):
    """
    Upload inspection and thermal PDFs to generate a Detailed Diagnostic Report.
    """
    request_start = time.time()
    logger.info("=" * 60)
    logger.info("🚀 NEW REPORT GENERATION REQUEST")
    logger.info(f"   Inspection file: {inspection.filename}")
    logger.info(f"   Thermal file: {thermal.filename}")
    logger.info("=" * 60)

    try:
        # Validate file types
        for upload, name in [(inspection, "inspection"), (thermal, "thermal")]:
            if not upload.filename.lower().endswith(".pdf"):
                logger.error(f"❌ Invalid file type for {name}: {upload.filename}")
                raise HTTPException(
                    status_code=400,
                    detail=f"{name} file must be a PDF. Got: {upload.filename}"
                )

        # Save uploaded files
        inspection_path = f"{UPLOAD_DIR}/inspection.pdf"
        thermal_path = f"{UPLOAD_DIR}/thermal.pdf"

        logger.info("💾 Saving uploaded files...")
        with open(inspection_path, "wb") as f:
            shutil.copyfileobj(inspection.file, f)
        with open(thermal_path, "wb") as f:
            shutil.copyfileobj(thermal.file, f)

        insp_size = os.path.getsize(inspection_path)
        therm_size = os.path.getsize(thermal_path)
        logger.info(f"   Inspection: {insp_size // 1024}KB | Thermal: {therm_size // 1024}KB")

        # Step 1: Extract text and images from both PDFs
        logger.info("📄 STEP 1: Extracting text and images...")
        step1_start = time.time()

        inspection_text, inspection_images = extract_pdf(inspection_path, "inspection")
        thermal_text, thermal_images = extract_pdf(thermal_path, "thermal")

        all_images = inspection_images + thermal_images
        step1_elapsed = time.time() - step1_start
        logger.info(f"   Step 1 complete: {len(all_images)} total images in {step1_elapsed:.2f}s")

        # Step 2: Generate DDR using LLM with full context
        logger.info("🤖 STEP 2: Generating DDR with Gemini AI...")
        step2_start = time.time()

        ddr = generate_ddr(
            inspection_text=inspection_text,
            thermal_text=thermal_text,
            images=all_images
        )

        step2_elapsed = time.time() - step2_start
        logger.info(f"   Step 2 complete in {step2_elapsed:.2f}s")

        if "error" in ddr:
            logger.error(f"❌ LLM returned error: {ddr['error']}")
            return JSONResponse(
                status_code=500,
                content=ddr
            )

        # Step 3: Resolve image references
        logger.info("🖼️ STEP 3: Resolving image references...")
        if "AreaWiseObservations" in ddr and isinstance(ddr["AreaWiseObservations"], list):
            ddr["AreaWiseObservations"] = map_images_to_observations(
                ddr["AreaWiseObservations"],
                all_images
            )

        total_elapsed = time.time() - request_start
        logger.info("=" * 60)
        logger.info(f"🎉 REPORT GENERATED SUCCESSFULLY in {total_elapsed:.2f}s")
        logger.info(f"   Breakdown: Extract={step1_elapsed:.2f}s | LLM={step2_elapsed:.2f}s")
        logger.info("=" * 60)

        return ddr

    except HTTPException:
        raise
    except Exception as e:
        total_elapsed = time.time() - request_start
        logger.error(f"❌ Request failed after {total_elapsed:.2f}s: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )


@app.post("/download-report")
async def download_report(ddr_data: dict):
    """
    Accept DDR JSON data and return a downloadable PDF report.
    """
    logger.info("📥 PDF download request received")
    try:
        pdf_buffer = generate_pdf(ddr_data)
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=DDR_Report.pdf"
            }
        )
    except Exception as e:
        logger.error(f"❌ PDF generation failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to generate PDF: {str(e)}"}
        )