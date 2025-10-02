import { useState, useEffect, useRef, useCallback } from "react";
import "./App.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// --- Helper Functions ---
const fmtTime = (ts) => {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
};
const uid = (prefix = "id") => prefix + Math.random().toString(36).slice(2, 9);

// --- Child Components ---

// Represents the animated log analysis placeholder.
// MODIFICATION: Removed the `onComplete` prop and related logic.
// This component is now purely for visual feedback while waiting for the API.

const LogAnalysisAnimation = ({ messageId, isComplete }) => {
  const step = "Analyzing Request...";
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    if (isComplete) {
      setCompleted(true);
    }
  }, [isComplete]);

  return (
    <div className="log-analysis-steps" id={`anim-${messageId}`}>
      <div className={`analysis-step ${completed ? "completed" : ""}`}>
        <div className="icon">
          {!completed && <div className="spinner"></div>}
          <svg
            className="checkmark"
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        <div className="text">{step}</div>
      </div>
    </div>
  );
};

// --- Main App Component ---
function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [chats, setChats] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [pendingFile, setPendingFile] = useState(null);
  const [inputValue, setInputValue] = useState("");

  const inputAreaRef = useRef(null);
  const fileInputRef = useRef(null);
  const chatWindowRef = useRef(null);

  // Initialize with some default chats
  useEffect(() => {
    const initialChats = [
      {
        id: uid("c_"),
        title: "Welcome Chat",
        messages: [
          {
            role: "assistant",
            text: "Hello! Paste logs or start a new chat. Click the paperclip to attach files.",
            time: Date.now() - 1000 * 60 * 6,
            id: uid("m_"),
          },
        ],
      },
      {
        id: uid("c_"),
        title: "Server errors",
        messages: [
          {
            role: "user",
            text: "There are many 500 errors in /api",
            time: Date.now() - 1000 * 60 * 60,
            id: uid("m_"),
          },
          {
            role: "assistant",
            text: "Check the Nginx logs and the app trace for exceptions.",
            time: Date.now() - 1000 * 60 * 58,
            id: uid("m_"),
          },
        ],
      },
      { id: uid("c_"), title: "Weekly report", messages: [] },
    ];
    setChats(initialChats);
    setActiveId(initialChats[0].id);
  }, []);

  // Scroll to bottom of chat window when messages change
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTo({
        top: chatWindowRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [chats, activeId]);

  // Auto-resize textarea
  const autoResize = () => {
    const el = inputAreaRef.current;
    if (el) {
      el.style.height = "auto";
      const h = Math.min(200, el.scrollHeight);
      el.style.height = `${h}px`;
    }
  };

  useEffect(autoResize, [inputValue]);

  // Toggle sidebar and global keydown listener for 's' key
  const handleToggleSidebar = () => setCollapsed((prev) => !prev);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (
        e.key.toLowerCase() === "s" &&
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey
      ) {
        if (document.activeElement !== inputAreaRef.current) {
          handleToggleSidebar();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const createChat = useCallback((title = "New Chat") => {
    const id = uid("c_");
    const newChat = { id, title, messages: [] };
    setChats((prev) => [newChat, ...prev]);
    setActiveId(id);
    return id;
  }, []);

  const handleNewChat = () => {
    createChat("Chat " + (chats.length + 1));
    if (collapsed) {
      setCollapsed(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) {
      setPendingFile(file);
    }
  };

  const removeAttachment = () => {
    setPendingFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // --- MODIFICATION: Updated sendMessage to call a backend API ---
  // --- MODIFICATION: Updated sendMessage to support streaming from backend ---
  const sendMessage = useCallback(
    async (text, file) => {
      let currentId = activeId;
      if (!currentId) {
        currentId = createChat();
      }

      const userMessage = {
        role: "user",
        text,
        time: Date.now(),
        file: file ? { name: file.name, size: file.size } : null,
        id: uid("m_"),
      };

      const tempAssistantMessage = {
        id: uid("m_"),
        role: "assistant",
        text: "%%LOG_ANALYSIS_PLACEHOLDER%%", // Will be filled gradually with stream
        time: Date.now(),
      };

      // Instantly update UI
      setChats((prevChats) =>
        prevChats.map((c) =>
          c.id === currentId
            ? {
                ...c,
                messages: [...c.messages, userMessage, tempAssistantMessage],
              }
            : c
        )
      );

      setInputValue("");
      removeAttachment();

      try {
        const formData = new FormData();
        formData.append("prompt", text);
        if (file) formData.append("file", file);

        const response = await fetch("http://localhost:5000/api/analyze", {
          method: "POST",
          body: formData,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Server error: ${response.status}`);
        }

        // Stream reader setup
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let accumulatedText = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          accumulatedText += chunk;

          // Update assistant message incrementally
          setChats((prevChats) =>
            prevChats.map((c) => {
              if (c.id === currentId) {
                return {
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === tempAssistantMessage.id
                      ? { ...m, text: accumulatedText }
                      : m
                  ),
                };
              }
              return c;
            })
          );
        }
      } catch (error) {
        console.error("Streaming failed:", error);
        const errorMessage = `Error: ${
          error.message || "Could not connect to the server."
        }`;

        setChats((prevChats) =>
          prevChats.map((c) => {
            if (c.id === currentId) {
              return {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === tempAssistantMessage.id
                    ? { ...m, text: errorMessage }
                    : m
                ),
              };
            }
            return c;
          })
        );
      }
    },
    [activeId, createChat]
  );

  const handleSendMessage = () => {
    const txt = inputValue.trim();
    if (!txt && !pendingFile) return; // Allow sending just a file
    sendMessage(txt, pendingFile);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim().length > 0 || pendingFile) handleSendMessage();
    }
  };

  // --- MODIFICATION: Removed `handleAnimationComplete` ---
  // This function is no longer needed as the response comes from the backend.

  const handleDeleteChat = (idToDelete) => {
    if (!window.confirm("Are you sure you want to delete this chat?")) return;
    setChats((prev) => {
      const newChats = prev.filter((c) => c.id !== idToDelete);
      if (activeId === idToDelete) {
        setActiveId(newChats.length > 0 ? newChats[0].id : null);
      }
      return newChats;
    });
  };

  const activeChat = chats.find((c) => c.id === activeId);

  return (
    <div className="app">
      <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="sidebar-top">
          <div className="brand" title="LogSage Lite">
            <div className="logo">
              <img
                src="https://img.icons8.com/pulsar-gradient/480/log.png"
                alt="logo"
              />
            </div>
            <div className="app-name">LogSage Lite</div>
          </div>
          <button
            className="toggle-btn"
            onClick={handleToggleSidebar}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand" : "Collapse"}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              {collapsed ? (
                <path
                  d="M9 6l6 6-6 6"
                  stroke="#E6EEF6"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ) : (
                <path
                  d="M15 18l-6-6 6-6"
                  stroke="#E6EEF6"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              )}
            </svg>
          </button>
        </div>

        <button className="new-chat" onClick={handleNewChat} title="New chat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 5v14M5 12h14"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ color: "var(--accent)" }}
            />
          </svg>
          <div className="label">New chat</div>
        </button>

        <div className="recent" aria-label="Recent chats">
          {chats.length === 0 ? (
            <div style={{ opacity: 0.4, padding: "12px" }}>
              No recent chats.
            </div>
          ) : (
            chats.map((c) => {
              const last = c.messages[c.messages.length - 1];
              const snippet = last?.text
                ? last.text.length > 60
                  ? last.text.slice(0, 60) + "..."
                  : last.text
                : "No messages yet";
              return (
                <div
                  key={c.id}
                  className={`chat-item ${c.id === activeId ? "active" : ""}`}
                  tabIndex={0}
                  onClick={() => setActiveId(c.id)}
                  onKeyDown={(e) => e.key === "Enter" && setActiveId(c.id)}
                >
                  {collapsed ? (
                    <div className="avatar" title={c.title}>
                      {c.title.slice(0, 1).toUpperCase()}
                    </div>
                  ) : (
                    <>
                      <div className="avatar">
                        {c.title.slice(0, 1).toUpperCase()}
                      </div>
                      <div className="ci-body">
                        <div className="ci-title">{c.title}</div>
                        <div style={{ display: "flex", alignItems: "center" }}>
                          <div className="ci-sub">{snippet}</div>
                          <div className="ci-time">{fmtTime(last?.time)}</div>
                        </div>
                      </div>
                      <button
                        className="delete-chat-btn"
                        data-id={c.id}
                        title="Delete chat"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteChat(c.id);
                        }}
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <line x1="18" y1="6" x2="6" y2="18"></line>
                          <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                      </button>
                    </>
                  )}
                </div>
              );
            })
          )}
        </div>

        <div className="sidebar-bottom">
          <div className="settings" title="Settings">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z"
                stroke="#A3AED0"
                strokeWidth="1.3"
              />
              <path
                d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06A2 2 0 1 1 2.27 17.9l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09c.63 0 1.18-.34 1.51-1a1.65 1.65 0 0 0-.33-1.82l-.06-.06A2 2 0 1 1 6.6 2.27l.06.06c.63.63.77 1.5.33 2.28-.36.62-.36 1.32 0 1.94.69.99 1.61 1.57 2.77 1.57H11a2 2 0 1 1 4 0h.09c1.16 0 2.08-.58 2.77-1.57.36-.62.36-1.32 0-1.94-.44-.78-.3-1.65.33-2.28l.06-.06A2 2 0 1 1 21.73 6.6l-.06.06c-.63.63-1 1.5-.54 2.28.36.62.36 1.32 0 1.94-.69.99-1.61 1.57-2.77 1.57H13a2 2 0 1 1-4 0H8.91c-.77 0-1.5.24-2.1.66"
                stroke="#A3AED0"
                strokeWidth="1.1"
              />
            </svg>
            <div style={{ opacity: 0.95 }}>Settings</div>
          </div>
        </div>
      </aside>

      <main className="main">
        <div className="chat-window" ref={chatWindowRef} aria-live="polite">
          {!activeChat ? (
            <div className="placeholder">Select or create a chat to start.</div>
          ) : activeChat.messages.length === 0 ? (
            <div className="placeholder">
              This chat is empty. Send a message to begin!
            </div>
          ) : (
            activeChat.messages.map((m) => (
              <div
                key={m.id}
                className={`msg ${m.role === "user" ? "user" : "assistant"}`}
              >
                {m.text === "%%LOG_ANALYSIS_PLACEHOLDER%%" ? (
                  // MODIFICATION: No longer passes `onComplete` prop
                  <LogAnalysisAnimation messageId={m.id} />
                ) : (
                  <>
                    <div className="text">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {m.text}
                      </ReactMarkdown>
                    </div>
                    {m.file && (
                      <div className="meta">Attachment: {m.file.name}</div>
                    )}
                    <div className="meta">{fmtTime(m.time)}</div>
                  </>
                )}
              </div>
            ))
          )}
        </div>

        <div className="composer">
          <button
            className="file-btn"
            title="Attach file"
            onClick={() => fileInputRef.current?.click()}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M21.44 11.05l-8.5 8.5a5.5 5.5 0 0 1-7.78-7.78l8.5-8.5a4 4 0 0 1 5.66 5.66l-8.5 8.5"
                stroke="#D1D5DB"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          <div className="input-wrap">
            <textarea
              id="inputArea"
              ref={inputAreaRef}
              rows="1"
              placeholder="Type your message or paste logs..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
            ></textarea>
            {pendingFile && (
              <div
                className="attachment-preview"
                onClick={removeAttachment}
                title="Click to remove"
              >
                {pendingFile.name}
              </div>
            )}
          </div>

          <button
            className="send-btn"
            disabled={inputValue.trim().length === 0 && !pendingFile}
            onClick={handleSendMessage}
            title="Send message"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2 .01 7z" />
            </svg>
          </button>

          <input
            type="file"
            id="fileInput"
            style={{ display: "none" }}
            ref={fileInputRef}
            onChange={handleFileChange}
          />
        </div>
      </main>
    </div>
  );
}

export default App;
