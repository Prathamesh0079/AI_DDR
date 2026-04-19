import React, { useState } from "react";
import UploadForm from "./UploadForm";
import ReportView from "./ReportView";
import "./App.css";

function App() {
  const [report, setReport] = useState(null);

  return (
    <div className="app-wrapper">
      <header className="app-header">
        <h1>🏗️ AI DDR Generator</h1>
        <p className="app-subtitle">
          Intelligent Detailed Diagnostic Report generation from inspection &amp; thermal data
        </p>
      </header>

      <main className="app-main">
        <UploadForm setReport={setReport} />
        {report && <ReportView report={report} />}
      </main>

      <footer className="app-footer">
        <p>Powered by Gemini AI · Built for professional building inspections</p>
      </footer>
    </div>
  );
}

export default App;