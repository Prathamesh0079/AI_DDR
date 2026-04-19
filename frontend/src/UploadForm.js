import React, { useState, useEffect, useRef } from "react";
import axios from "axios";

function UploadForm({ setReport }) {
    const [inspection, setInspection] = useState(null);
    const [thermal, setThermal] = useState(null);
    const [loading, setLoading] = useState(false);
    const [progress, setProgress] = useState("");
    const [elapsed, setElapsed] = useState(0);
    const timerRef = useRef(null);

    // Live elapsed timer during generation
    useEffect(() => {
        if (loading) {
            setElapsed(0);
            timerRef.current = setInterval(() => {
                setElapsed((prev) => prev + 1);
            }, 1000);
        } else {
            clearInterval(timerRef.current);
        }
        return () => clearInterval(timerRef.current);
    }, [loading]);

    const handleSubmit = async () => {
        if (!inspection || !thermal) {
            alert("Please upload both PDFs before generating the report.");
            return;
        }

        const formData = new FormData();
        formData.append("inspection", inspection);
        formData.append("thermal", thermal);

        try {
            setLoading(true);
            setReport(null);
            setProgress("Uploading documents and analyzing with AI...");

            const res = await axios.post(
                "http://127.0.0.1:8000/generate-report",
                formData,
                { timeout: 300000 } // 5 minute timeout
            );

            setReport(res.data);
            setProgress("");
        } catch (err) {
            let message;
            if (err.code === "ECONNABORTED") {
                message = "Request timed out. The AI is taking too long — try with smaller PDFs or fewer images.";
            } else {
                message = err.response?.data?.error || err.message || "Unknown error";
            }
            alert(`Error generating report: ${message}`);
            setProgress("");
        } finally {
            setLoading(false);
        }
    };

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
    };

    return (
        <div className="upload-container">
            <h3>📂 Upload Inspection Documents</h3>

            <div className="upload-field">
                <label>Inspection Report (PDF)</label>
                <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => setInspection(e.target.files[0])}
                    disabled={loading}
                />
                {inspection && <span className="file-name">✅ {inspection.name}</span>}
            </div>

            <div className="upload-field">
                <label>Thermal Report (PDF)</label>
                <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => setThermal(e.target.files[0])}
                    disabled={loading}
                />
                {thermal && <span className="file-name">✅ {thermal.name}</span>}
            </div>

            <button
                className="generate-btn"
                onClick={handleSubmit}
                disabled={loading}
            >
                {loading ? "⏳ Generating..." : "🚀 Generate DDR Report"}
            </button>

            {loading && (
                <div className="progress-section">
                    <p className="progress-text">{progress}</p>
                    <p className="elapsed-text">⏱️ Elapsed: {formatTime(elapsed)}</p>
                </div>
            )}
        </div>
    );
}

export default UploadForm;