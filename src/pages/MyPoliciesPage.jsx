import React, { useEffect } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  FileText,
  MessageSquare,
  ShieldAlert,
  Trash2,
  Upload,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { deleteDocument, getMyDocuments } from "../api";
import { useApp } from "../context/AppContext";
import { useDocumentUpload } from "../hooks";

export default function MyPoliciesPage() {
  const navigate = useNavigate();
  const { addDocument, myDocuments, removeDocument, setChatContext, setMyDocuments } = useApp();
  const { progress, upload, uploading } = useDocumentUpload();

  useEffect(() => {
    getMyDocuments()
      .then((docs) => setMyDocuments(docs))
      .catch(() => {});
  }, [setMyDocuments]);

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    const doc = await upload(file);
    if (doc) {
      addDocument(doc);
    }

    event.target.value = "";
  };

  const handleDelete = async (docId) => {
    await deleteDocument(docId);
    removeDocument(docId);
  };

  const handleChat = (doc) => {
    setChatContext({ type: "document", id: doc.doc_id, label: doc.filename });
    navigate("/chat");
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div className="page-header">
        <div className="page-header-copy">
          <p className="page-header-kicker">Document Workspace</p>
          <h1 className="display-md" style={{ marginBottom: "var(--sp-2)" }}>
            Upload and manage your policy documents
          </h1>
          <p className="body-sm">
            Keep personal policy files ready for document-scoped questions and delete them whenever you want.
          </p>
        </div>
      </div>

      <div className="status-banner status-banner-info" style={{ marginBottom: "var(--sp-6)" }}>
        <ShieldAlert size={16} color="var(--c-primary)" style={{ flexShrink: 0, marginTop: 1 }} />
        <div>
          <strong style={{ color: "var(--c-text-1)" }}>Privacy note:</strong> uploaded documents should be redacted server-side and can be deleted later along with the derived index.
        </div>
      </div>

      <div
        className="card-ghost"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          const file = event.dataTransfer.files?.[0];
          if (file) {
            upload(file).then((doc) => {
              if (doc) {
                addDocument(doc);
              }
            });
          }
        }}
        style={{
          padding: "var(--sp-10)",
          textAlign: "center",
          marginBottom: "var(--sp-8)",
          cursor: uploading ? "not-allowed" : "pointer",
          position: "relative",
          background: "rgba(255,255,255,0.02)",
          borderRadius: "var(--r-lg)",
        }}
      >
        <input
          accept=".pdf,.jpg,.jpeg,.png"
          disabled={uploading}
          onChange={handleFileChange}
          style={{ position: "absolute", inset: 0, opacity: 0, cursor: uploading ? "not-allowed" : "pointer" }}
          type="file"
        />
        <div
          style={{
            width: 58,
            height: 58,
            margin: "0 auto var(--sp-4)",
            borderRadius: "var(--r-md)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "var(--c-primary-soft)",
            border: "1px solid rgba(111,182,255,0.14)",
          }}
        >
          <Upload color="var(--c-primary-strong)" size={26} />
        </div>
        <p style={{ fontWeight: 700, marginBottom: "var(--sp-1)", fontSize: "1rem" }}>
          {uploading ? "Uploading document..." : "Drop your policy document here"}
        </p>
        <p className="body-sm">Supports PDF, JPG, PNG. Max 20MB.</p>

        {uploading ? (
          <div style={{ marginTop: "var(--sp-5)" }}>
            <div
              style={{
                height: 6,
                background: "rgba(255,255,255,0.06)",
                borderRadius: "var(--r-full)",
                overflow: "hidden",
                maxWidth: 320,
                margin: "0 auto",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${progress}%`,
                  background: "linear-gradient(90deg, var(--c-primary), var(--c-primary-strong))",
                  borderRadius: "var(--r-full)",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
            <p style={{ fontSize: "0.75rem", color: "var(--c-text-3)", marginTop: "var(--sp-2)" }}>{progress}%</p>
          </div>
        ) : null}
      </div>

      {!myDocuments.length ? (
        <div className="empty-state">
          <FileText size={32} style={{ margin: "0 auto var(--sp-3)", color: "var(--c-text-4)" }} />
          <p style={{ fontWeight: 700, color: "var(--c-text-1)" }}>No documents uploaded yet</p>
          <p style={{ fontSize: "0.82rem", marginTop: "var(--sp-1)" }}>
            Upload your policy PDF to start asking document-specific questions.
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-3)" }}>
          <div className="results-strip" style={{ marginBottom: "var(--sp-1)" }}>
            <p className="heading-sm">Uploaded Documents</p>
            <span className="badge">{myDocuments.length} files</span>
          </div>
          {myDocuments.map((doc) => (
            <DocRow key={doc.doc_id} doc={doc} onChat={handleChat} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  );
}

function DocRow({ doc, onChat, onDelete }) {
  const statusIcon =
    doc.status === "ready" ? (
      <CheckCircle2 color="var(--c-success)" size={15} />
    ) : doc.status === "processing" ? (
      <Clock3 color="var(--c-warn)" size={15} />
    ) : (
      <AlertCircle color={doc.status === "low_confidence" ? "var(--c-warn)" : "var(--c-danger)"} size={15} />
    );

  const statusLabel =
    doc.status === "ready"
      ? "Ready"
      : doc.status === "processing"
        ? "Processing..."
        : doc.status === "low_confidence"
          ? "Low confidence - verify manually"
          : "Error";

  return (
    <div className="card" style={{ display: "flex", alignItems: "center", gap: "var(--sp-4)" }}>
      <div
        style={{
          width: 48,
          height: 48,
          flexShrink: 0,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.05)",
          borderRadius: "var(--r-md)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <FileText color="var(--c-text-3)" size={20} />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontWeight: 700, fontSize: "0.95rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {doc.filename}
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)", marginTop: 6, flexWrap: "wrap" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.78rem" }}>
            {statusIcon}
            <span style={{ color: doc.status === "ready" ? "var(--c-success)" : "var(--c-warn)" }}>{statusLabel}</span>
          </span>
          {doc.page_count ? <span style={{ fontSize: "0.75rem", color: "var(--c-text-3)" }}>{doc.page_count} pages</span> : null}
          {doc.extraction_confidence && doc.extraction_confidence < 80 ? (
            <span className="stale-tag">OCR confidence {doc.extraction_confidence}%</span>
          ) : null}
          {doc.uploaded_at ? (
            <span style={{ fontSize: "0.72rem", color: "var(--c-text-3)" }}>
              {new Date(doc.uploaded_at).toLocaleDateString("en-IN")}
            </span>
          ) : null}
        </div>
      </div>

      <div style={{ display: "flex", gap: "var(--sp-2)", flexShrink: 0 }}>
        <button
          className="btn btn-ghost btn-sm"
          disabled={doc.status !== "ready"}
          onClick={() => onChat(doc)}
          title="Chat about this document"
          type="button"
        >
          <MessageSquare size={14} />
          Ask
        </button>
        <button
          className="btn btn-danger btn-sm"
          onClick={() => onDelete(doc.doc_id)}
          title="Delete document and index"
          type="button"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
