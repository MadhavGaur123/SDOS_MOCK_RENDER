import React, { useEffect, useRef, useState } from "react";
import { AlertCircle, BookOpen, Bot, Send, ShieldCheck, User } from "lucide-react";
import { useChat } from "../../hooks";

export default function ChatPanel({ contextType, contextId, contextLabel }) {
  const { messages, sendMessage, streaming } = useChat(contextType, contextId);
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || streaming) {
      return;
    }

    sendMessage(input.trim());
    setInput("");
    inputRef.current?.focus();
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0)), var(--c-surface)",
        border: "1px solid var(--c-border)",
        borderRadius: "var(--r-lg)",
        overflow: "hidden",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div
        style={{
          padding: "var(--sp-5)",
          borderBottom: "1px solid rgba(255,255,255,0.05)",
          display: "flex",
          justifyContent: "space-between",
          gap: "var(--sp-3)",
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-3)" }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: "var(--r-md)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "var(--c-primary-soft)",
              border: "1px solid rgba(111,182,255,0.14)",
            }}
          >
            <Bot size={18} color="var(--c-primary-strong)" />
          </div>

          <div>
            <p style={{ fontSize: "0.94rem", fontWeight: 700 }}>Policy Assistant</p>
            {contextLabel ? (
              <p style={{ fontSize: "0.76rem", color: "var(--c-text-3)" }}>Context: {contextLabel}</p>
            ) : null}
          </div>
        </div>

        <span className="badge badge-primary">
          <ShieldCheck size={12} />
          Evidence-linked
        </span>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "var(--sp-5)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--sp-5)",
          background: "linear-gradient(180deg, rgba(255,255,255,0.01), transparent)",
        }}
      >
        {messages.length === 0 ? (
          <EmptyState
            contextLabel={contextLabel}
            onSelectPrompt={(prompt) => {
              setInput(prompt);
              inputRef.current?.focus();
            }}
          />
        ) : null}

        {messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}

        {streaming ? <TypingDots /> : null}
        <div ref={bottomRef} />
      </div>

      <div
        style={{
          padding: "var(--sp-4)",
          borderTop: "1px solid rgba(255,255,255,0.05)",
          display: "flex",
          gap: "var(--sp-3)",
          alignItems: "flex-end",
          background: "rgba(255,255,255,0.015)",
        }}
      >
        <textarea
          ref={inputRef}
          className="input-field"
          disabled={streaming}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about coverage, waiting periods, exclusions, or claims..."
          rows={1}
          style={{
            flex: 1,
            resize: "none",
            minHeight: 46,
            maxHeight: 128,
            overflowY: "auto",
            lineHeight: 1.55,
          }}
          value={input}
        />

        <button
          className="btn btn-primary btn-sm"
          disabled={!input.trim() || streaming}
          onClick={handleSend}
          style={{ height: 46, padding: "0 var(--sp-4)", flexShrink: 0 }}
          type="button"
        >
          <Send size={15} />
        </button>
      </div>

      <div
        style={{
          padding: "var(--sp-2) var(--sp-4)",
          borderTop: "1px solid rgba(255,255,255,0.05)",
          fontSize: "0.72rem",
          color: "var(--c-text-3)",
          textAlign: "center",
        }}
      >
        Responses are grounded in policy documents. Always verify final coverage with the official wording.
      </div>
    </div>
  );
}

function Message({ message }) {
  const isUser = message.role === "user";

  return (
    <div
      style={{
        display: "flex",
        gap: "var(--sp-3)",
        flexDirection: isUser ? "row-reverse" : "row",
        alignItems: "flex-start",
      }}
    >
      <div
        style={{
          width: 30,
          height: 30,
          flexShrink: 0,
          borderRadius: isUser ? "var(--r-md)" : "var(--r-full)",
          background: isUser ? "rgba(255,255,255,0.05)" : "var(--c-primary-soft)",
          border: `1px solid ${isUser ? "rgba(255,255,255,0.06)" : "rgba(111,182,255,0.16)"}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {isUser ? <User size={14} color="var(--c-text-2)" /> : <Bot size={14} color="var(--c-primary-strong)" />}
      </div>

      <div style={{ maxWidth: "80%" }}>
        <div
          style={{
            background: isUser ? "rgba(255,255,255,0.035)" : "rgba(255,255,255,0.02)",
            border: `1px solid ${isUser ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.04)"}`,
            borderRadius: isUser
              ? "var(--r-lg) var(--r-sm) var(--r-lg) var(--r-lg)"
              : "var(--r-sm) var(--r-lg) var(--r-lg) var(--r-lg)",
            padding: "var(--sp-3) var(--sp-4)",
            fontSize: "0.88rem",
            lineHeight: 1.7,
            color: message.error ? "var(--c-danger)" : "var(--c-text-1)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {message.content || <span style={{ opacity: 0.4 }}>...</span>}
        </div>

        {message.citations?.length ? (
          <div style={{ marginTop: "var(--sp-2)", display: "flex", flexWrap: "wrap", gap: "var(--sp-1)" }}>
            {message.citations.map((citation, index) => (
              <span key={`${citation.section || citation.page}-${index}`} className="citation" title={citation.text}>
                <BookOpen size={10} />
                {citation.section || `p.${citation.page}`}
              </span>
            ))}
          </div>
        ) : null}

        {message.caveat ? (
          <div
            style={{
              marginTop: "var(--sp-2)",
              display: "flex",
              gap: "var(--sp-2)",
              alignItems: "flex-start",
              background: "rgba(229, 169, 92, 0.09)",
              border: "1px solid rgba(229, 169, 92, 0.18)",
              borderRadius: "var(--r-sm)",
              padding: "var(--sp-2) var(--sp-3)",
              fontSize: "0.76rem",
              color: "var(--c-warn)",
            }}
          >
            <AlertCircle size={12} style={{ flexShrink: 0, marginTop: 1 }} />
            {message.caveat}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        alignItems: "center",
        width: "fit-content",
        padding: "10px 14px",
        borderRadius: "var(--r-lg)",
        border: "1px solid rgba(255,255,255,0.05)",
        background: "rgba(255,255,255,0.02)",
      }}
    >
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "var(--c-text-3)",
            animation: "typingBounce 1.2s infinite",
            animationDelay: `${index * 0.2}s`,
            display: "block",
          }}
        />
      ))}
      <style>{`
        @keyframes typingBounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.35; }
          30% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function EmptyState({ contextLabel, onSelectPrompt }) {
  const prompts = contextLabel
    ? [
        "What is the PED waiting period?",
        "Is maternity covered in this policy?",
        "What are the major exclusions?",
        "How does cashless claim work?",
        "What is the room rent limit?",
      ]
    : [
        "Compare maternity coverage between policies",
        "Which policy has the best restoration benefit?",
        "What does PED waiting period mean?",
      ];

  return (
    <div style={{ textAlign: "center", padding: "var(--sp-8) var(--sp-4)" }}>
      <div
        style={{
          width: 54,
          height: 54,
          margin: "0 auto var(--sp-4)",
          borderRadius: "var(--r-md)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--c-primary-soft)",
          border: "1px solid rgba(111,182,255,0.14)",
        }}
      >
        <Bot size={24} color="var(--c-primary-strong)" />
      </div>
      <p style={{ fontWeight: 700, marginBottom: "var(--sp-1)" }}>Ask anything about your policy</p>
      <p style={{ fontSize: "0.84rem", color: "var(--c-text-3)", marginBottom: "var(--sp-5)" }}>
        Start with a common question or type your own. Answers are presented with evidence references when available.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-2)" }}>
        {prompts.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onSelectPrompt(prompt)}
            style={{
              background: "rgba(255,255,255,0.02)",
              border: "1px solid rgba(255,255,255,0.05)",
              borderRadius: "var(--r-md)",
              color: "var(--c-text-2)",
              cursor: "pointer",
              fontSize: "0.82rem",
              fontWeight: 600,
              padding: "var(--sp-3) var(--sp-4)",
              textAlign: "left",
              transition: "all var(--t-fast)",
            }}
            type="button"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
