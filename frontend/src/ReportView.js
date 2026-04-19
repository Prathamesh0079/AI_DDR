import React, { useState } from "react";
import axios from "axios";

function ReportView({ report }) {
    const [downloading, setDownloading] = useState(false);

    // Helper: safely convert a value to an array (LLM sometimes returns strings)
    const toArray = (val) => {
        if (Array.isArray(val)) return val;
        if (typeof val === "string" && val.trim()) return [val];
        return [];
    };

    const handleDownloadPDF = async () => {
        try {
            setDownloading(true);
            const res = await axios.post(
                "http://127.0.0.1:8000/download-report",
                report,
                {
                    responseType: "blob",
                    timeout: 30000,
                }
            );

            // Create download link
            const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
            const link = document.createElement("a");
            link.href = url;
            link.setAttribute("download", "DDR_Report.pdf");
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            alert("PDF download failed. Please try again.");
            console.error(err);
        } finally {
            setDownloading(false);
        }
    };

    const site = report.SiteMetadata || {};

    return (
        <div className="report-view">
            <div className="report-header">
                <h2>📋 Detailed Diagnostic Report</h2>
                <button
                    className="download-btn"
                    onClick={handleDownloadPDF}
                    disabled={downloading}
                >
                    {downloading ? "⏳ Generating PDF..." : "📥 Download PDF"}
                </button>
            </div>

            {/* Site Metadata */}
            {Object.keys(site).length > 0 && (
                <section className="report-section site-info-section">
                    <h3>🏗️ Site Information</h3>
                    <table className="site-info-table">
                        <tbody>
                            {site.ClientName && site.ClientName !== "Not Available" && (
                                <tr><td className="info-label">Client / Owner</td><td>{site.ClientName}</td></tr>
                            )}
                            {site.SiteAddress && site.SiteAddress !== "Not Available" && (
                                <tr><td className="info-label">Site Address</td><td>{site.SiteAddress}</td></tr>
                            )}
                            {site.PreparedFor && site.PreparedFor !== "Not Available" && (
                                <tr><td className="info-label">Prepared For</td><td>{site.PreparedFor}</td></tr>
                            )}
                            {site.TypeOfStructure && site.TypeOfStructure !== "Not Available" && (
                                <tr><td className="info-label">Type of Structure</td><td>{site.TypeOfStructure}</td></tr>
                            )}
                            {site.Floors && site.Floors !== "Not Available" && (
                                <tr><td className="info-label">Floors</td><td>{site.Floors}</td></tr>
                            )}
                            {site.YearOfConstruction && site.YearOfConstruction !== "Not Available" && (
                                <tr><td className="info-label">Year of Construction</td><td>{site.YearOfConstruction}</td></tr>
                            )}
                            {site.AgeOfBuilding && site.AgeOfBuilding !== "Not Available" && (
                                <tr><td className="info-label">Age of Building</td><td>{site.AgeOfBuilding}</td></tr>
                            )}
                            {site.DateOfInspection && site.DateOfInspection !== "Not Available" && (
                                <tr><td className="info-label">Date of Inspection</td><td>{site.DateOfInspection}</td></tr>
                            )}
                            {site.InspectedBy && site.InspectedBy !== "Not Available" && (
                                <tr><td className="info-label">Inspected By</td><td>{site.InspectedBy}</td></tr>
                            )}
                        </tbody>
                    </table>
                </section>
            )}

            {/* Section 1: Property Issue Summary */}
            <section className="report-section">
                <h3>🏠 Property Issue Summary</h3>
                <p>{report.PropertyIssueSummary || "Not Available"}</p>
            </section>

            {/* Section 2: Area-wise Observations */}
            <section className="report-section">
                <h3>🔍 Area-wise Observations</h3>
                {toArray(report.AreaWiseObservations).length > 0 ? (
                    toArray(report.AreaWiseObservations).map((obs, i) => (
                        <div key={i} className="observation-card">
                            <div className="obs-header">
                                <span className="obs-area">{obs.area}</span>
                                <span className={`severity-badge severity-${obs.severity?.toLowerCase()}`}>
                                    {obs.severity}
                                </span>
                            </div>
                            <p className="obs-issue"><strong>Issue:</strong> {obs.issue}</p>
                            <p className="obs-reasoning"><strong>Reasoning:</strong> {obs.reasoning}</p>
                            {obs.thermal_finding && obs.thermal_finding !== "Not Available" && (
                                <p className="obs-thermal">
                                    <strong>🌡️ Thermal Finding:</strong> {obs.thermal_finding}
                                </p>
                            )}

                            {/* Images with captions */}
                            <div className="obs-images">
                                {toArray(obs.images).length > 0 ? (
                                    toArray(obs.images).map((img, j) => (
                                        img !== "Image Not Available" ? (
                                            <div key={j} className="obs-image-wrapper">
                                                <img
                                                    src={`http://127.0.0.1:8000/${img}`}
                                                    alt={`${obs.area} observation ${j + 1}`}
                                                    className="obs-image"
                                                />
                                                {toArray(obs.image_captions)[j] && (
                                                    <p className="image-caption">
                                                        {toArray(obs.image_captions)[j]}
                                                    </p>
                                                )}
                                            </div>
                                        ) : (
                                            <p key={j} className="no-image">📷 Image Not Available</p>
                                        )
                                    ))
                                ) : (
                                    <p className="no-image">📷 Image Not Available</p>
                                )}
                            </div>
                        </div>
                    ))
                ) : (
                    <p>No observations available.</p>
                )}
            </section>

            {/* Impact Summary Table */}
            {toArray(report.ImpactSummaryTable).length > 0 && (
                <section className="report-section">
                    <h3>📊 Impact Summary — Source vs. Symptom</h3>
                    <table className="impact-summary-table">
                        <thead>
                            <tr>
                                <th>Impacted Area (Symptom)</th>
                                <th>Source Area (Root)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {toArray(report.ImpactSummaryTable).map((row, i) => (
                                <tr key={i}>
                                    <td>{row.impacted_area || "—"}</td>
                                    <td>{row.source_area || "—"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </section>
            )}

            {/* Section 3: Probable Root Cause */}
            <section className="report-section">
                <h3>🔬 Probable Root Cause</h3>
                <p>{report.ProbableRootCause || "Not Available"}</p>
            </section>

            {/* Section 4: Severity Assessment */}
            <section className="report-section">
                <h3>⚠️ Severity Assessment</h3>
                <p>{report.SeverityAssessment || "Not Available"}</p>
            </section>

            {/* Section 5: Recommended Actions */}
            <section className="report-section">
                <h3>✅ Recommended Actions</h3>
                {toArray(report.RecommendedActions).length > 0 ? (
                    <ol className="action-list">
                        {toArray(report.RecommendedActions).map((action, i) => (
                            <li key={i}>{action}</li>
                        ))}
                    </ol>
                ) : (
                    <p>Not Available</p>
                )}
            </section>

            {/* Section 6: Additional Notes */}
            <section className="report-section">
                <h3>📝 Additional Notes</h3>
                <p>{report.AdditionalNotes || "Not Available"}</p>
            </section>

            {/* Section 7: Missing or Unclear Information */}
            <section className="report-section">
                <h3>❓ Missing or Unclear Information</h3>
                {toArray(report.MissingOrUnclearInformation).length > 0 ? (
                    <ul className="missing-list">
                        {toArray(report.MissingOrUnclearInformation).map((item, i) => (
                            <li key={i}>{item}</li>
                        ))}
                    </ul>
                ) : (
                    <p>Not Available</p>
                )}
            </section>
        </div>
    );
}

export default ReportView;