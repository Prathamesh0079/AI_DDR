import React from "react";

function ReportView({ report }) {
    return (
        <div style={{ marginTop: "30px" }}>
            <h2>DDR Report</h2>

            <h3>Summary</h3>
            <p>{report.PropertyIssueSummary}</p>

            <h3>Observations</h3>
            {report.AreaWiseObservations?.map((obs, i) => (
                <div key={i} style={{ border: "1px solid #ccc", padding: "10px", margin: "10px 0" }}>
                    <strong>{obs.area}</strong>
                    <p>{obs.issue}</p>
                    <p><b>Severity:</b> {obs.severity}</p>
                    <p><b>Reason:</b> {obs.reasoning}</p>

                    {obs.image !== "Image Not Available" && (
                        <img
                            src={`http://127.0.0.1:8000/${obs.image}`}
                            alt="obs"
                            style={{ width: "200px" }}
                        />
                    )}
                </div>
            ))}

            <h3>Root Cause</h3>
            <p>{report.ProbableRootCause}</p>

            <h3>Severity Assessment</h3>
            <p>{report.SeverityAssessment}</p>

            <h3>Recommended Actions</h3>
            <ul>
                {report.RecommendedActions?.map((a, i) => (
                    <li key={i}>{a}</li>
                ))}
            </ul>

            <h3>Additional Notes</h3>
            <p>{report.AdditionalNotes}</p>

            <h3>Missing Info</h3>
            <ul>
                {report.MissingOrUnclearInformation?.map((m, i) => (
                    <li key={i}>{m}</li>
                ))}
            </ul>
        </div>
    );
}

export default ReportView;