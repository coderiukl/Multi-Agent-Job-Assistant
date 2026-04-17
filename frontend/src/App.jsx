import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { getMe, login, logout, register } from "./api/auth";
import {
  createConversation,
  deleteConversation,
  getConversations,
  getMessages,
  streamChat,
} from "./api/conversations";
import { getCvs, uploadCv, deleteCv } from "./api/cvs";
import { getMatchingJobs } from "./api/match";

const suggestionPrompts = [
  { icon: "📄", text: "Phân tích CV của tôi", sub: "Đánh giá điểm mạnh & yếu" },
  { icon: "🎯", text: "So khớp CV với JD Backend Developer", sub: "Tỉ lệ phù hợp chi tiết" },
  { icon: "🔍", text: "Tìm job phù hợp với CV hiện tại", sub: "Gợi ý từ cơ sở dữ liệu" },
  { icon: "💡", text: "Gợi ý kỹ năng tôi còn thiếu", sub: "Dựa trên xu hướng thị trường" },
];

export default function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [authLoading, setAuthLoading] = useState(false);
  const [authForm, setAuthForm] = useState({ email: "", password: "", full_name: "" });

  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);

  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const [cvFiles, setCvFiles] = useState([]);
  const [selectedCvId, setSelectedCvId] = useState(() => localStorage.getItem("selected_cv_id") || "");
  const [selectedUploadFile, setSelectedUploadFile] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);

  const [matchedJobs, setMatchedJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [error, setError] = useState("");

  const fileInputRef = useRef(null);
  const chatBodyRef = useRef(null);
  const textareaRef = useRef(null);

  const activeConversation = useMemo(
    () => conversations.find((c) => c.id === activeConversationId) || null,
    [conversations, activeConversationId]
  );

  // Persist CV selection
  useEffect(() => {
    if (selectedCvId) localStorage.setItem("selected_cv_id", selectedCvId);
  }, [selectedCvId]);

  useEffect(() => { bootstrap(); }, []);

  useEffect(() => {
    if (activeConversationId) loadMessages(activeConversationId);
  }, [activeConversationId]);

  useEffect(() => {
    chatBodyRef.current?.scrollTo({ top: chatBodyRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isTyping]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [input]);

  async function bootstrap() {
    try {
      const me = await getMe();
      setUser(me);
      await Promise.all([loadConversations(), loadCvs()]);
    } catch { /* not logged in */ }
  }

  async function loadConversations() {
    try {
      const data = await getConversations();
      setConversations(data);
      if (data.length > 0 && !activeConversationId) {
        setActiveConversationId(data[0].id);
      }
    } catch (err) { setError(err.message); }
  }

  async function loadMessages(conversationId) {
    try {
      const data = await getMessages(conversationId);
      // data giờ là { messages, matched_jobs }
      setMessages(data.messages || data); // tương thích cả 2 format
      if (data.matched_jobs?.length) {
        setMatchedJobs(data.matched_jobs);
      } else {
        setMatchedJobs([]);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadCvs() {
    try {
      const data = await getCvs();
      const items = data.items || [];
      setCvFiles(items);
      // Giữ selectedCvId nếu vẫn tồn tại, nếu không thì auto-chọn cái đầu
      const storedId = localStorage.getItem("selected_cv_id");
      const stillExists = items.some((cv) => cv.id === storedId);
      if (!stillExists && items.length > 0) {
        setSelectedCvId(items[0].id);
      }
    } catch (err) { setError(err.message); }
  }

  async function handleAuthSubmit(e) {
    e.preventDefault();
    setError("");
    setAuthLoading(true);
    try {
      if (authMode === "register") {
        await register({ email: authForm.email, password: authForm.password, full_name: authForm.full_name });
      }
      await login({ email: authForm.email, password: authForm.password });
      const me = await getMe();
      setUser(me);
      await Promise.all([loadConversations(), loadCvs()]);
    } catch (err) { setError(err.message); }
    finally { setAuthLoading(false); }
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
    localStorage.removeItem("selected_cv_id");
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
    } catch (err) { setError(err.message); }
  }

  async function handleDeleteConversation(e, conversationId) {
    e.stopPropagation();
    try {
      await deleteConversation(conversationId);
      const next = conversations.filter((c) => c.id !== conversationId);
      setConversations(next);
      if (activeConversationId === conversationId) {
        setActiveConversationId(next[0]?.id || null);
        setMessages([]);
        setMatchedJobs([]);
      }
    } catch (err) { setError(err.message); }
  }

  async function handleUploadCv() {
    if (!selectedUploadFile) return;
    setUploadLoading(true);
    setError("");
    try {
      const uploaded = await uploadCv(selectedUploadFile);
      await loadCvs();
      setSelectedCvId(uploaded.id);
      setSelectedUploadFile(null);
    } catch (err) { setError(err.message); }
    finally { setUploadLoading(false); }
  }

  async function handleFindJobsFromCv() {
    if (!selectedCvId) { setError("Bạn chưa chọn CV"); return; }
    setJobsLoading(true);
    setMatchedJobs([]);
    setError("");
    try {
      const jobs = await getMatchingJobs(selectedCvId, 10);
      setMatchedJobs(jobs);
    } catch (err) { setError(err.message); }
    finally { setJobsLoading(false); }
  }

  async function handleSend() {
    if (!input.trim() && !selectedUploadFile) return;
    setError("");
    // KHÔNG xóa matchedJobs ở đây — chỉ xóa khi stream trả về done

    let conversationId = activeConversationId;
    try {
      if (!conversationId) {
        const newConv = await createConversation("Cuộc trò chuyện mới");
        setConversations((prev) => [newConv, ...prev]);
        setActiveConversationId(newConv.id);
        conversationId = newConv.id;
      }

      const tempUserId = crypto.randomUUID();
      const tempAssistantId = crypto.randomUUID();

      setMessages((prev) => [
        ...prev,
        {
          id: tempUserId,
          role: "user",
          content: input.trim() || `Đã gửi file: ${selectedUploadFile?.name}`,
          created_at: new Date().toISOString(),
        },
        { id: tempAssistantId, role: "assistant", content: "", created_at: new Date().toISOString() },
      ]);
      setIsTyping(true);

      const sentInput = input.trim();
      const sentFile = selectedUploadFile;
      setInput("");
      setSelectedUploadFile(null);

      await streamChat({
        conversationId,
        message: sentInput,
        cvId: selectedCvId || undefined,
        file: sentFile || undefined,
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
          if (payload?.matched_jobs?.length) {
            setMatchedJobs(payload.matched_jobs);
          }
          // Reload messages để có id thật từ DB
          await Promise.all([loadMessages(conversationId), loadConversations(), loadCvs()]);
        },
        onError: (errMessage) => {
          setError(errMessage || "Có lỗi khi stream chat");
          setIsTyping(false);
        },
      });
    } catch (err) {
      setError(err.message);
      setIsTyping(false);
    }
  }

  function handleKeyDown(e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }

  async function handleDeleteCv(e, cvId) {
    e.stopPropagation();
    if (!confirm("Xóa CV này?")) return;
    try {
      await deleteCv(cvId);
      if (selectedCvId === cvId) {
        setSelectedCvId("");
        localStorage.removeItem("selected_cv_id");
      }
      await loadCvs();
    } catch (err) {
      setError(err.message);
    }
  }
  // ── AUTH SCREEN ──────────────────────────────────────────────────────────
  if (!user) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <div className="auth-logo">✦</div>
          <div className="auth-badge">Multi-Agent Job Assistant</div>
          <h1>{authMode === "login" ? "Đăng nhập" : "Tạo tài khoản"}</h1>
          <p>Phân tích CV · So khớp JD · Tìm việc phù hợp bằng AI</p>

          <form onSubmit={handleAuthSubmit} className="auth-form">
            {authMode === "register" && (
              <input type="text" placeholder="Họ và tên"
                value={authForm.full_name}
                onChange={(e) => setAuthForm((p) => ({ ...p, full_name: e.target.value }))}
              />
            )}
            <input type="email" placeholder="Email" value={authForm.email}
              onChange={(e) => setAuthForm((p) => ({ ...p, email: e.target.value }))}
            />
            <input type="password" placeholder="Mật khẩu" value={authForm.password}
              onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))}
            />
            <button type="submit" disabled={authLoading} className="primary-btn">
              {authLoading ? "Đang xử lý..." : authMode === "login" ? "Đăng nhập" : "Đăng ký"}
            </button>
          </form>

          <button className="switch-auth-btn"
            onClick={() => setAuthMode((p) => (p === "login" ? "register" : "login"))}>
            {authMode === "login" ? "Chưa có tài khoản? Đăng ký" : "Đã có tài khoản? Đăng nhập"}
          </button>
          {error && <div className="error-box">{error}</div>}
        </div>
      </div>
    );
  }

  // ── MAIN APP ─────────────────────────────────────────────────────────────
  return (
    <div className="app-shell">
      {/* SIDEBAR */}
      <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="sidebar-header">
          <button className="sidebar-toggle" onClick={() => setCollapsed(!collapsed)}>☰</button>
          {!collapsed && (
            <button className="new-chat-btn" onClick={handleNewChat}>+ Cuộc trò chuyện mới</button>
          )}
        </div>

        {!collapsed && (
          <>
            <div className="sidebar-group">
              <div className="sidebar-group-title">Hội thoại</div>
              <div className="conversation-list">
                {conversations.map((item) => (
                  <div key={item.id}
                    className={`conversation-item ${activeConversationId === item.id ? "active" : ""}`}
                    onClick={() => { setActiveConversationId(item.id); setMatchedJobs([]); }}
                  >
                    <div className="conversation-main">
                      <div className="conversation-title">{item.title || "Cuộc trò chuyện"}</div>
                      <div className="conversation-time">{formatDate(item.created_at)}</div>
                    </div>
                    <button className="delete-conv-btn"
                      onClick={(e) => handleDeleteConversation(e, item.id)}>×</button>
                  </div>
                ))}
                {conversations.length === 0 && (
                  <div className="empty-sidebar-hint">Chưa có hội thoại nào</div>
                )}
              </div>
            </div>

            <div className="sidebar-group">
              <div className="sidebar-group-title">CV của bạn</div>

              <div className="cv-list">
                {cvFiles.map((cv) => (
                  <div key={cv.id}
                    className={`cv-item ${selectedCvId === cv.id ? "active" : ""}`}
                    onClick={() => setSelectedCvId(cv.id)}
                  >
                    <span className="cv-item-name" title={cv.original_name}>
                      {cv.original_name}
                    </span>
                    <button className="delete-conv-btn"
                      onClick={(e) => handleDeleteCv(e, cv.id)}>×</button>
                  </div>
                ))}
                {cvFiles.length === 0 && (
                  <div className="empty-sidebar-hint">Chưa có CV nào</div>
                )}
              </div>

              <button className="secondary-btn full-btn" onClick={handleFindJobsFromCv}
                disabled={jobsLoading || !selectedCvId}>
                {jobsLoading ? "Đang tìm..." : "Tìm jobs phù hợp"}
              </button>

              <div className="cv-upload-area">
                <input ref={fileInputRef} type="file" accept=".pdf,.doc,.docx" hidden
                  onChange={(e) => setSelectedUploadFile(e.target.files?.[0] || null)} />

                {selectedUploadFile ? (
                  <div className="file-preview-mini">
                    <span className="file-preview-name">📄 {selectedUploadFile.name}</span>
                    <div className="file-preview-actions">
                      <button className="primary-btn small-btn" onClick={handleUploadCv}
                        disabled={uploadLoading}>
                        {uploadLoading ? "Uploading..." : "Upload"}
                      </button>
                      <button className="ghost-btn small-btn"
                        onClick={() => setSelectedUploadFile(null)}>Hủy</button>
                    </div>
                  </div>
                ) : (
                  <button className="upload-cv-btn" onClick={() => fileInputRef.current?.click()}>
                    + Tải lên CV mới
                  </button>
                )}
              </div>
            </div>

            <div className="sidebar-footer">
              <div className="user-card">
                <div className="user-avatar-bubble">
                  {(user.full_name || user.email || "U").charAt(0).toUpperCase()}
                </div>
                <div className="user-info">
                  <div className="user-name">{user.full_name || "Người dùng"}</div>
                  <div className="user-email">{user.email}</div>
                </div>
              </div>
              <button className="logout-btn" onClick={handleLogout}>Đăng xuất</button>
            </div>
          </>
        )}
      </aside>

      {/* MAIN CHAT */}
      <main className="chat-layout">
        <header className="chat-header">
          <div className="chat-header-left">
            <h1>{activeConversation?.title || "Job Assistant"}</h1>
            <p>Phân tích CV · So khớp JD · Tìm việc phù hợp</p>
          </div>
          {selectedCvId && (
            <div className="chat-header-cv-badge">
              📄 {cvFiles.find((c) => c.id === selectedCvId)?.original_name || "CV đã chọn"}
            </div>
          )}
        </header>

        <section className="chat-body" ref={chatBodyRef}>
          {/* EMPTY STATE */}
          {!messages.length && (
            <div className="empty-state">
              <div className="hero-logo">✦</div>
              <h2>Hôm nay bạn muốn làm gì?</h2>
              <p>Tải CV, nhập câu hỏi hoặc yêu cầu hệ thống phân tích hồ sơ của bạn như một trợ lý tuyển dụng AI.</p>
              <div className="suggestion-grid">
                {suggestionPrompts.map((item) => (
                  <button key={item.text} className="suggestion-card"
                    onClick={() => { setInput(item.text); textareaRef.current?.focus(); }}>
                    <div className="suggestion-icon">{item.icon}</div>
                    <div className="suggestion-title">{item.text}</div>
                    <div className="suggestion-sub">{item.sub}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* MESSAGES */}
          <div className="messages-container">
            {messages.map((msg) => (
              <div key={msg.id}
                className={`message-row ${msg.role === "user" ? "user-row" : "assistant-row"}`}>
                <div className={`avatar ${msg.role === "user" ? "user-avatar-bubble" : "ai-avatar"}`}>
                  {msg.role === "assistant" ? "AI" : (user.full_name || "B").charAt(0).toUpperCase()}
                </div>
                <div className="message-content">
                  <div className="message-author">
                    {msg.role === "assistant" ? "Job Assistant" : (user.full_name || "Bạn")}
                  </div>
                  <div className="message-text">
                    {msg.role === "assistant" ? (
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    ) : (
                      <p>{msg.content}</p>
                    )}
                  </div>
                  <div className="message-time">{formatDate(msg.created_at)}</div>
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="message-row assistant-row">
                <div className="avatar ai-avatar">AI</div>
                <div className="message-content">
                  <div className="message-author">Job Assistant</div>
                  <div className="typing-bubble"><span/><span/><span/></div>
                </div>
              </div>
            )}
          </div>

          {/* JOB RESULTS */}
          {jobsLoading && (
            <div className="jobs-loading">
              <div className="spinner" />
              <span>Đang tìm kiếm công việc phù hợp...</span>
            </div>
          )}

          {!!matchedJobs.length && !jobsLoading && (
            <div className="result-section">
              <div className="result-title">
                Công việc phù hợp
                <span className="result-count">{matchedJobs.length} kết quả</span>
              </div>
              <div className="job-grid">
                {matchedJobs.map((job, index) => (
                  <div className="job-card" key={job.id || index}>
                    <div className="job-card-top">
                      <div className="job-card-info">
                        <div className="job-title">{job.title}</div>
                        <div className="job-company">{job.company || "Chưa rõ công ty"}</div>
                      </div>
                      <div className="job-score-badge">
                        {typeof job.score === "number"
                          ? `${Math.round(job.score * 100)}%`
                          : job.score}
                      </div>
                    </div>

                    <div className="job-meta">
                      {job.location && <span>📍 {job.location}</span>}
                      {job.contract_type && <span>💼 {job.contract_type}</span>}
                      {job.experience_required && <span>⏱ {job.experience_required}</span>}
                    </div>

                    {(job.salary_raw || (job.salary_min && job.salary_max)) && (
                      <div className="job-salary">
                        💰 {job.salary_raw || `${job.salary_min?.toLocaleString()} - ${job.salary_max?.toLocaleString()} VNĐ`}
                      </div>
                    )}

                    {job.technical_skills && (
                      <div className="job-skills">
                        {job.technical_skills.split(",").slice(0, 4).map((s) => (
                          <span key={s} className="skill-tag">{s.trim()}</span>
                        ))}
                      </div>
                    )}

                    {job.url && (
                      <a href={job.url} target="_blank" rel="noreferrer" className="job-link">
                        Xem chi tiết →
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && <div className="error-box inline-error">{error}</div>}
        </section>

        {/* FOOTER COMPOSER */}
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
              <button className="remove-file-btn" onClick={() => setSelectedUploadFile(null)}>×</button>
            </div>
          )}

          <div className="composer-shell">
            <button className="composer-icon-btn"
              onClick={() => fileInputRef.current?.click()} title="Đính kèm file">
              +
            </button>
            <textarea ref={textareaRef} value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedCvId ? "Nhập tin nhắn... (CV đã chọn)" : "Nhập tin nhắn cho Job Assistant..."}
              rows={1}
            />
            <button className="send-btn" onClick={handleSend}
              disabled={isTyping || (!input.trim() && !selectedUploadFile)}>
              ↑
            </button>
          </div>
          <div className="footer-note">Enter để gửi · Shift+Enter xuống dòng</div>
        </footer>
      </main>
    </div>
  );
}

function formatDate(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}