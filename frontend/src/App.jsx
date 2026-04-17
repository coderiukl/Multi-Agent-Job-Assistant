import { useEffect, useMemo, useRef, useState } from "react";
import { getMe, login, logout, register } from "./api/auth";
import {
  createConversation,
  deleteConversation,
  getConversations,
  getMessages,
  streamChat,
} from "./api/conversations";
import { getCvs, uploadCv } from "./api/cvs";
import { getMatchingJobs } from "./api/match";

const suggestionPrompts = [
  "Phân tích CV của tôi",
  "So khớp CV với mô tả công việc Backend Developer",
  "Gợi ý kỹ năng tôi còn thiếu",
  "Tìm job phù hợp với CV hiện tại",
];

export default function App() {
  const [collapsed, setCollapsed] = useState(false);

  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [authLoading, setAuthLoading] = useState(false);
  const [authForm, setAuthForm] = useState({
    email: "",
    password: "",
    full_name: "",
  });

  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);

  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const [cvFiles, setCvFiles] = useState([]);
  const [selectedCvId, setSelectedCvId] = useState("");
  const [selectedUploadFile, setSelectedUploadFile] = useState(null);

  const [matchedJobs, setMatchedJobs] = useState([]);
  const [error, setError] = useState("");

  const fileInputRef = useRef(null);
  const chatBodyRef = useRef(null);
  const textareaRef = useRef(null);

  const activeConversation = useMemo(() => {
    return conversations.find((c) => c.id === activeConversationId) || null;
  }, [conversations, activeConversationId]);

  useEffect(() => {
    bootstrap();
  }, []);

  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId);
    }
  }, [activeConversationId]);

  useEffect(() => {
    chatBodyRef.current?.scrollTo({
      top: chatBodyRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isTyping]);

  useEffect(() => {
    autoResizeTextarea();
  }, [input]);

  function autoResizeTextarea() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }

  async function bootstrap() {
    try {
      const me = await getMe();
      setUser(me);
      await Promise.all([loadConversations(), loadCvs()]);
    } catch {
      //
    }
  }

  async function loadConversations() {
    try {
      const data = await getConversations();
      setConversations(data);
      if (data.length > 0 && !activeConversationId) {
        setActiveConversationId(data[0].id);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadMessages(conversationId) {
    try {
      const data = await getMessages(conversationId);
      setMessages(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadCvs() {
    try {
      const data = await getCvs();
      setCvFiles(data.items || []);
      if (!selectedCvId && data.items?.length) {
        setSelectedCvId(data.items[0].id);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleAuthSubmit(e) {
    e.preventDefault();
    setError("");
    setAuthLoading(true);

    try {
      if (authMode === "login") {
        await login({
          email: authForm.email,
          password: authForm.password,
        });
      } else {
        await register({
          email: authForm.email,
          password: authForm.password,
          full_name: authForm.full_name,
        });

        await login({
          email: authForm.email,
          password: authForm.password,
        });
      }

      const me = await getMe();
      setUser(me);
      await Promise.all([loadConversations(), loadCvs()]);
    } catch (err) {
      setError(err.message);
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleLogout() {
    await logout();
    setUser(null);
    setConversations([]);
    setActiveConversationId(null);
    setMessages([]);
    setCvFiles([]);
    setSelectedCvId("");
    setMatchedJobs([]);
  }

  async function handleNewChat() {
    try {
      const conv = await createConversation("Cuộc trò chuyện mới");
      setConversations((prev) => [conv, ...prev]);
      setActiveConversationId(conv.id);
      setMessages([]);
      setMatchedJobs([]);
      setInput("");
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteConversation(conversationId) {
    try {
      await deleteConversation(conversationId);
      const next = conversations.filter((c) => c.id !== conversationId);
      setConversations(next);

      if (activeConversationId === conversationId) {
        setActiveConversationId(next[0]?.id || null);
        setMessages([]);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  function handleSuggestionClick(text) {
    setInput(text);
    textareaRef.current?.focus();
  }

  function handleChooseFile() {
    fileInputRef.current?.click();
  }

  function handleSelectLocalFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedUploadFile(file);
  }

  async function handleUploadCvOnly() {
    if (!selectedUploadFile) return;

    try {
      const uploaded = await uploadCv(selectedUploadFile);
      await loadCvs();
      setSelectedCvId(uploaded.id);
      setSelectedUploadFile(null);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleFindJobsFromCv() {
    if (!selectedCvId) {
      setError("Bạn chưa chọn CV");
      return;
    }

    try {
      const jobs = await getMatchingJobs(selectedCvId, 10);
      setMatchedJobs(jobs);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSend() {
    if (!input.trim() && !selectedUploadFile) return;

    setError("");
    setMatchedJobs([]);

    let conversationId = activeConversationId;

    try {
      if (!conversationId) {
        const newConv = await createConversation("Cuộc trò chuyện mới");
        setConversations((prev) => [newConv, ...prev]);
        setActiveConversationId(newConv.id);
        conversationId = newConv.id;
      }

      const tempUserMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: input.trim() || `Đã gửi file: ${selectedUploadFile?.name}`,
        created_at: new Date().toISOString(),
      };

      const tempAssistantId = crypto.randomUUID();

      setMessages((prev) => [
        ...prev,
        tempUserMessage,
        {
          id: tempAssistantId,
          role: "assistant",
          content: "",
          created_at: new Date().toISOString(),
        },
      ]);

      setIsTyping(true);

      await streamChat({
        conversationId,
        message: input.trim(),
        cvId: selectedCvId || undefined,
        file: selectedUploadFile || undefined,
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === tempAssistantId
                ? { ...msg, content: (msg.content || "") + token }
                : msg
            )
          );
        },
        onDone: async (payload) => {
          setIsTyping(false);

          if (payload?.matched_jobs) {
            setMatchedJobs(payload.matched_jobs);
          }

          await Promise.all([
            loadMessages(conversationId),
            loadConversations(),
            loadCvs(),
          ]);
        },
        onError: (errMessage) => {
          setError(errMessage || "Có lỗi khi stream chat");
          setIsTyping(false);
        },
      });

      setInput("");
      setSelectedUploadFile(null);
    } catch (err) {
      setError(err.message);
      setIsTyping(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  if (!user) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <div className="auth-badge">Multi-Agent Job Assistant</div>
          <h1>{authMode === "login" ? "Đăng nhập" : "Tạo tài khoản"}</h1>
          <p>
            Giao diện chatbot kiểu ChatGPT dành cho phân tích CV, matching JD và gợi ý việc làm.
          </p>

          <form onSubmit={handleAuthSubmit} className="auth-form">
            {authMode === "register" && (
              <input
                type="text"
                placeholder="Họ và tên"
                value={authForm.full_name}
                onChange={(e) =>
                  setAuthForm((prev) => ({ ...prev, full_name: e.target.value }))
                }
              />
            )}

            <input
              type="email"
              placeholder="Email"
              value={authForm.email}
              onChange={(e) =>
                setAuthForm((prev) => ({ ...prev, email: e.target.value }))
              }
            />

            <input
              type="password"
              placeholder="Mật khẩu"
              value={authForm.password}
              onChange={(e) =>
                setAuthForm((prev) => ({ ...prev, password: e.target.value }))
              }
            />

            <button type="submit" disabled={authLoading} className="primary-btn">
              {authLoading
                ? "Đang xử lý..."
                : authMode === "login"
                ? "Đăng nhập"
                : "Đăng ký"}
            </button>
          </form>

          <button
            className="switch-auth-btn"
            onClick={() =>
              setAuthMode((prev) => (prev === "login" ? "register" : "login"))
            }
          >
            {authMode === "login"
              ? "Chưa có tài khoản? Đăng ký"
              : "Đã có tài khoản? Đăng nhập"}
          </button>

          {error && <div className="error-box">{error}</div>}
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="sidebar-header">
          <button className="sidebar-toggle" onClick={() => setCollapsed(!collapsed)}>
            ☰
          </button>

          {!collapsed && (
            <button className="new-chat-btn" onClick={handleNewChat}>
              + Cuộc trò chuyện mới
            </button>
          )}
        </div>

        {!collapsed && (
          <>
            <div className="sidebar-group">
              <div className="sidebar-group-title">Hội thoại</div>

              <div className="conversation-list">
                {conversations.map((item) => (
                  <div
                    key={item.id}
                    className={`conversation-item ${
                      activeConversationId === item.id ? "active" : ""
                    }`}
                  >
                    <button
                      className="conversation-main"
                      onClick={() => setActiveConversationId(item.id)}
                    >
                      <div className="conversation-title">{item.title}</div>
                      <div className="conversation-time">
                        {formatDate(item.created_at)}
                      </div>
                    </button>

                    <button
                      className="delete-conv-btn"
                      onClick={() => handleDeleteConversation(item.id)}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="sidebar-group">
              <div className="sidebar-group-title">CV của bạn</div>

              <select
                className="cv-select"
                value={selectedCvId}
                onChange={(e) => setSelectedCvId(e.target.value)}
              >
                <option value="">-- Chọn CV --</option>
                {cvFiles.map((cv) => (
                  <option key={cv.id} value={cv.id}>
                    {cv.original_name}
                  </option>
                ))}
              </select>

              <button className="secondary-btn full-btn" onClick={handleFindJobsFromCv}>
                Tìm jobs phù hợp
              </button>
            </div>

            <div className="sidebar-footer">
              <div className="user-card">
                <div className="user-avatar">
                  {(user.full_name || user.email || "U").charAt(0).toUpperCase()}
                </div>
                <div className="user-info">
                  <div className="user-name">{user.full_name || "Người dùng"}</div>
                  <div className="user-email">{user.email}</div>
                </div>
              </div>

              <button className="logout-btn" onClick={handleLogout}>
                Đăng xuất
              </button>
            </div>
          </>
        )}
      </aside>

      <main className="chat-layout">
        <header className="chat-header">
          <div className="chat-header-left">
            <h1>{activeConversation?.title || "Job Assistant"}</h1>
            <p>Phân tích CV • So khớp JD • Tìm việc phù hợp</p>
          </div>

          <div className="chat-header-actions">
            <button className="header-btn" onClick={handleChooseFile}>
              Chọn file
            </button>
            <button className="header-btn primary-soft" onClick={handleUploadCvOnly}>
              Upload CV
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              hidden
              onChange={handleSelectLocalFile}
            />
          </div>
        </header>

        <section className="chat-body" ref={chatBodyRef}>
          {!messages.length && (
            <div className="empty-state">
              <div className="hero-logo">✦</div>
              <h2>Hôm nay bạn muốn làm gì?</h2>
              <p>
                Tải CV, nhập câu hỏi hoặc yêu cầu hệ thống phân tích hồ sơ của bạn như một trợ lý tuyển dụng AI.
              </p>

              <div className="suggestion-grid">
                {suggestionPrompts.map((item) => (
                  <button
                    key={item}
                    className="suggestion-card"
                    onClick={() => handleSuggestionClick(item)}
                  >
                    <div className="suggestion-title">{item}</div>
                    <div className="suggestion-sub">
                      Bắt đầu nhanh với prompt có sẵn
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="messages-container">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`message-row ${
                  msg.role === "user" ? "user-row" : "assistant-row"
                }`}
              >
                <div className={`avatar ${msg.role === "user" ? "user-avatar-bubble" : ""}`}>
                  {msg.role === "assistant" ? "AI" : "B"}
                </div>

                <div className="message-content">
                  <div className="message-author">
                    {msg.role === "assistant" ? "Job Assistant" : "Bạn"}
                  </div>
                  <div className="message-text">
                    <p>{msg.content}</p>
                  </div>
                  <div className="message-time">{formatDate(msg.created_at)}</div>
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="message-row assistant-row">
                <div className="avatar">AI</div>
                <div className="message-content">
                  <div className="message-author">Job Assistant</div>
                  <div className="typing-bubble">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {!!matchedJobs.length && (
            <div className="result-section">
              <div className="result-title">Công việc phù hợp</div>

              <div className="job-grid">
                {matchedJobs.map((job, index) => (
                  <div className="job-card" key={job.id || index}>
                    <div className="job-card-top">
                      <div>
                        <div className="job-title">{job.title}</div>
                        <div className="job-company">{job.company || "Chưa rõ công ty"}</div>
                      </div>
                      <div className="job-score">
                        {typeof job.score === "number"
                          ? job.score.toFixed(3)
                          : job.score}
                      </div>
                    </div>

                    <div className="job-meta">
                      <span>{job.location || "N/A"}</span>
                      <span>{job.contract_type || "N/A"}</span>
                    </div>

                    {job.salary_raw && (
                      <div className="job-salary">{job.salary_raw}</div>
                    )}

                    {job.url && (
                      <a href={job.url} target="_blank" rel="noreferrer" className="job-link">
                        Xem chi tiết
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && <div className="error-box inline-error">{error}</div>}
        </section>

        <footer className="chat-footer">
          {selectedUploadFile && (
            <div className="file-preview">
              <div className="file-preview-left">
                <div className="file-icon">📄</div>
                <div>
                  <div className="file-name">{selectedUploadFile.name}</div>
                  <div className="file-size">{formatFileSize(selectedUploadFile.size)}</div>
                </div>
              </div>
              <button className="remove-file-btn" onClick={() => setSelectedUploadFile(null)}>
                ×
              </button>
            </div>
          )}

          <div className="composer-shell">
            <button className="composer-icon-btn" onClick={handleChooseFile}>
              +
            </button>

            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Nhập tin nhắn cho Job Assistant..."
              rows={1}
            />

            <button className="send-btn" onClick={handleSend}>
              ↑
            </button>
          </div>

          <div className="footer-note">
            Enter để gửi • Shift + Enter để xuống dòng
          </div>
        </footer>
      </main>
    </div>
  );
}

function formatDate(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);

  return d.toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
  });
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}