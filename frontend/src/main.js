import {
  deleteConversationHistory,
  getConversationHistory,
  searchJobs,
  sendConversationMessage,
  uploadCv,
} from "./api.js";

import "./styles.css";


const MAX_FILE_SIZE = 10 * 1024 * 1024;
const CONVERSATION_THREAD_KEY = "multi-agent-job-assistant-thread-id";
const CONVERSATION_THREADS_KEY = "multi-agent-job-assistant-conversation-threads";

const MAX_SAVED_CONVERSATIONS = 30;
const MAX_CONVERSATION_TITLE_LENGTH = 55;

const state = {
  threadId: getOrCreateThreadId(),
  conversationThreads: loadConversationThreads(),
  messages: [],

  selectedCvFile: null,
  uploadedCvId: null,
  cvUploadStatus: "idle",
  cvUploadRequestId: 0,

  matchingMode: false,
  jobDescription: "",
  currentMatchingResult: null,
  currentCvAnalysisResult: null,
  currentCareerAdviceResult: null,
  currentCoverLetterResult: null,

  currentWorkflow: null,
  workflowJobMatches: [],

  isSending: false,
  jobs: [],
  currentSearchResult: null,
  lastSearchQuery: "",
  currentSort: "relevance",

  selectedJob: null,
  activeWorkspacePanel: "chat",
  historyOpen: true,
  resultsOpen: false,
  resultsAvailable: false,
  lastFocusedBeforeDrawer: null,
};

const elements = {
  sidebarNewChatButton: document.querySelector("#sidebar-new-chat-button"),
  toggleHistoryButton: document.querySelector("#toggle-history-button"),
  conversationHistoryList: document.querySelector("#conversation-history-list"),
  conversationHistoryEmpty: document.querySelector("#conversation-history-empty"),

  newChatButton: document.querySelector("#new-chat-button"),
  toggleResultsButton: document.querySelector("#toggle-results-button"),
  workspace: document.querySelector(".workspace"),
  mobileTabs: document.querySelector(".mobile-workspace-tabs"),
  mobileTabButtons: document.querySelectorAll(".mobile-tab"),
  mobileResultsTab: document.querySelector("#mobile-results-tab"),
  mobileResultsBadge: document.querySelector("#mobile-results-badge"),

  messageList: document.querySelector("#message-list"),
  suggestionList: document.querySelector("#suggestion-list"),
  composerActions: document.querySelector("#composer-actions"),
  chatForm: document.querySelector("#chat-form"),
  messageInput: document.querySelector("#message-input"),
  sendButton: document.querySelector("#send-button"),
  toggleJdButton: document.querySelector("#toggle-jd-button"),
  jobDescriptionPanel: document.querySelector("#job-description-panel"),
  jobDescriptionSummary: document.querySelector("#job-description-summary"),
  jobDescriptionInput: document.querySelector("#job-description-input"),
  jobDescriptionCount: document.querySelector("#job-description-count"),
  editJdButton: document.querySelector("#edit-jd-button"),
  clearJdButton: document.querySelector("#clear-jd-button"),

  cvInput: document.querySelector("#cv-input"),
  attachCvButton: document.querySelector("#attach-cv-button"),
  removeCvButton: document.querySelector("#remove-cv-button"),
  selectedCv: document.querySelector("#selected-cv"),
  selectedCvName: document.querySelector("#selected-cv-name"),
  selectedCvStatus: document.querySelector("#selected-cv-status"),
  cvStatusBadge: document.querySelector("#cv-status-badge"),

  globalError: document.querySelector("#global-error"),

  resultsPanel: document.querySelector("#results-panel"),
  jobResults: document.querySelector("#job-results"),
  resultsSummary: document.querySelector("#results-summary"),
  resultCount: document.querySelector("#result-count"),
  searchStrategy: document.querySelector("#search-strategy"),
  activeFilters: document.querySelector("#active-filters"),
  jobSort: document.querySelector("#job-sort"),
  resultsEyebrow: document.querySelector("#results-eyebrow"),
  resultsTitle: document.querySelector("#results-title"),
  backToJobsButton: document.querySelector("#back-to-jobs-button"),
  closeResultsButton: document.querySelector("#close-results-button"),

  jobDetailOverlay: document.querySelector("#job-detail-overlay"),
  jobDetailDrawer: document.querySelector("#job-detail-drawer"),
  jobDetailContent: document.querySelector("#job-detail-content"),
  closeJobDetailButton: document.querySelector("#close-job-detail"),
};

function createThreadId() {
  return crypto.randomUUID();
}

function getOrCreateThreadId() {
  try {
    const storedThreadId = localStorage.getItem(
      CONVERSATION_THREAD_KEY,
    );

    if (storedThreadId) {
      return storedThreadId;
    }

    const threadId = createThreadId();

    localStorage.setItem(
      CONVERSATION_THREAD_KEY,
      threadId,
    );

    return threadId;
  } catch {
    return createThreadId();
  }
}


function saveThreadId(threadId) {
  state.threadId = threadId;

  try {
    localStorage.setItem(
      CONVERSATION_THREAD_KEY,
      threadId,
    );
  } catch {
    // The current tab can still use the generated thread ID.
  }
}

function loadConversationThreads() {
  try {
    const storedValue = localStorage.getItem(
      CONVERSATION_THREADS_KEY,
    );

    if (!storedValue) {
      return [];
    }

    const parsedValue = JSON.parse(storedValue);

    if (!Array.isArray(parsedValue)) {
      return [];
    }

    return parsedValue
      .filter(
        (item) =>
          typeof item?.threadId === "string" &&
          typeof item?.title === "string" &&
          typeof item?.updatedAt === "string" &&
          item?.isDraft !== true,
      )
      .slice(0, MAX_SAVED_CONVERSATIONS);
  } catch {
    return [];
  }
}


function saveConversationThreads() {
  try {
    localStorage.setItem(
      CONVERSATION_THREADS_KEY,
      JSON.stringify(state.conversationThreads),
    );
  } catch {
    // The conversation itself can still work without the sidebar index.
  }
}


function rememberConversationThread({
  threadId,
  firstMessage,
}) {
  const existingThread = state.conversationThreads.find(
    (thread) => thread.threadId === threadId,
  );

  const nextThread = {
    threadId,
    title:
      existingThread?.title ??
      createConversationTitle(firstMessage),
    updatedAt: new Date().toISOString(),
  };

  state.conversationThreads = [
    nextThread,
    ...state.conversationThreads.filter(
      (thread) => thread.threadId !== threadId,
    ),
  ].slice(0, MAX_SAVED_CONVERSATIONS);

  saveConversationThreads();
  renderConversationHistory();
}

function createConversationTitle(message) {
  const normalizedMessage = String(message ?? "")
    .replace(/\s+/g, " ")
    .trim();

  if (!normalizedMessage) {
    return "Cuộc trò chuyện mới";
  }

  if (
    normalizedMessage.length <=
    MAX_CONVERSATION_TITLE_LENGTH
  ) {
    return normalizedMessage;
  }

  return (
    normalizedMessage.slice(
      0,
      MAX_CONVERSATION_TITLE_LENGTH - 1,
    ).trimEnd() + "…"
  );
}

function renderConversationHistory() {
  const list = elements.conversationHistoryList;
  const emptyState = elements.conversationHistoryEmpty;

  if (!list || !emptyState) {
    return;
  }

  list.innerHTML = "";

  emptyState.hidden =
    state.conversationThreads.length > 0;

  for (const thread of state.conversationThreads) {
    const row = document.createElement("div");
    const button = document.createElement("button");
    const deleteButton = document.createElement("button");

    row.className = "conversation-history-row";
    button.type = "button";
    button.className = "conversation-history-item";
    button.dataset.threadId = thread.threadId;

    deleteButton.type = "button";
    deleteButton.className = "conversation-history-delete";
    deleteButton.dataset.deleteThreadId = thread.threadId;
    deleteButton.setAttribute(
      "aria-label",
      `Xóa cuộc trò chuyện ${thread.title}`,
    );
    deleteButton.title = "Xóa cuộc trò chuyện";
    deleteButton.textContent = "×";

    const isActive = thread.threadId === state.threadId;

    button.classList.toggle("is-active", isActive);

    if (isActive) {
      button.setAttribute("aria-current", "true");
    }

    const title = document.createElement("span");

    title.className = "conversation-history-title";
    title.textContent = thread.title;

    const time = document.createElement("span");

    time.className = "conversation-history-time";
    time.textContent = formatConversationTime(
      thread.updatedAt,
    );

    button.append(title, time);
    row.append(button, deleteButton);
    list.append(row);
  }
}


function formatConversationTime(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const today = new Date();
  const isToday =
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate();

  if (isToday) {
    return new Intl.DateTimeFormat("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

async function handleConversationHistoryClick(event) {
  const deleteButton = event.target.closest(
    "[data-delete-thread-id]",
  );

  if (deleteButton) {
    await deleteConversationThread(
      deleteButton.dataset.deleteThreadId,
    );
    return;
  }

  const button = event.target.closest(
    "[data-thread-id]",
  );

  if (!button) {
    return;
  }

  const threadId = button.dataset.threadId;

  if (!threadId || threadId === state.threadId) {
    return;
  }

  saveThreadId(threadId);

  // Reload để reset toàn bộ workspace và gọi API restore history.
  window.location.reload();
}


async function deleteConversationThread(threadId) {
  if (!threadId) {
    return;
  }

  const thread = state.conversationThreads.find(
    (item) => item.threadId === threadId,
  );
  const confirmed = window.confirm(
    `Xóa cuộc trò chuyện “${thread?.title ?? "này"}”?`,
  );

  if (!confirmed) {
    return;
  }

  try {
    await deleteConversationHistory(threadId);
  } catch (error) {
    showError(
      error?.message ??
      "Không thể xóa cuộc trò chuyện.",
    );
    return;
  }

  state.conversationThreads = state.conversationThreads.filter(
    (item) => item.threadId !== threadId,
  );
  saveConversationThreads();

  if (threadId === state.threadId) {
    resetConversation();
    return;
  }

  renderConversationHistory();
}

initializeApplication().catch((error) => {
  console.error(
    "Application initialization failed:",
    error,
  );
});


async function initializeApplication() {
  bindEvents();
  resizeMessageInput();
  setActiveWorkspacePanel("chat");
  updateComposerContext();
  showInitialJobState();
  renderConversationHistory();

  const restored = await restoreConversationHistory();

  if (!restored) {
    addWelcomeMessage();
  }
}

async function restoreConversationHistory() {
  try {
    const history = await getConversationHistory(
      state.threadId,
    );

    if (!history.messages.length) {
      return false;
    }

    saveThreadId(history.threadId);

    for (const message of history.messages) {
      addMessage({
        role: message.role,
        text: message.text,
      });
    }

    const firstUserMessage = history.messages.find(
      (message) => message.role === "user",
    );

    if (firstUserMessage) {
      rememberConversationThread({
        threadId: history.threadId,
        firstMessage: firstUserMessage.text,
      });
    }

    elements.suggestionList.hidden = true;

    return true;
  } catch (error) {
    console.warn(
      "Conversation history could not be restored:",
      error,
    );

    return false;
  }
}


function addWelcomeMessage() {
  addMessage({
    role: "assistant",
    text:
      "Xin chào! Mình là Job Search AI. Mình có thể giúp bạn " +
      "tìm việc, phân tích CV và tư vấn định hướng nghề nghiệp.",
  });
}

function bindEvents() {
  elements.messageInput.addEventListener(
    "input",
    () => {
      resizeMessageInput();
      updateSendButton();
    },
  );

  elements.messageInput.addEventListener(
    "keydown",
    (event) => {
      if (
        event.key === "Enter" &&
        !event.shiftKey
      ) {
        event.preventDefault();
        elements.chatForm.requestSubmit();
      }
    },
  );

  elements.chatForm.addEventListener(
    "submit",
    handleSubmit,
  );

  elements.toggleJdButton.addEventListener(
    "click",
    () => setMatchingMode(!state.matchingMode),
  );

  elements.jobDescriptionInput.addEventListener(
    "input",
    handleJobDescriptionInput,
  );

  elements.mobileTabs?.addEventListener(
    "click",
    handleMobileTabClick,
  );

  elements.clearJdButton.addEventListener(
    "click",
    clearJobDescription,
  );

  elements.editJdButton?.addEventListener(
    "click",
    showJobDescriptionEditor,
  );

  elements.attachCvButton.addEventListener(
    "click",
    () => {
      elements.cvInput.click();
    },
  );

  elements.cvInput.addEventListener(
    "change",
    handleCvSelection,
  );

  elements.removeCvButton.addEventListener(
    "click",
    removeCv,
  );

  elements.newChatButton.addEventListener(
    "click",
    resetConversation,
  );

  elements.toggleResultsButton?.addEventListener(
    "click",
    toggleResultsPanel,
  );
  
  elements.sidebarNewChatButton?.addEventListener(
    "click",
    resetConversation,
  );

  elements.toggleHistoryButton?.addEventListener(
    "click",
    toggleConversationHistory,
  );

  elements.conversationHistoryList?.addEventListener(
    "click",
    handleConversationHistoryClick,
  );

  elements.suggestionList.addEventListener(
    "click",
    handleSuggestionClick,
  );

  elements.composerActions?.addEventListener(
    "click",
    handleSuggestionClick,
  );

  elements.jobResults.addEventListener(
    "click",
    handleJobResultClick,
  );

  elements.jobSort.addEventListener(
    "change",
    handleSortChange,
  );

  elements.backToJobsButton?.addEventListener(
    "click",
    showJobSearchResultsFromState,
  );

  elements.closeResultsButton?.addEventListener(
    "click",
    closeResultsPanel,
  );

  elements.closeJobDetailButton.addEventListener(
    "click",
    closeJobDetail,
  );

  elements.jobDetailOverlay.addEventListener(
    "click",
    closeJobDetail,
  );

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeJobDetail();
      return;
    }

    if (
      event.key === "Tab" &&
      isJobDetailOpen()
    ) {
      trapJobDetailFocus(event);
    }
  });
}


function handleMobileTabClick(event) {
  const button = event.target.closest("[data-panel]");

  if (!button) {
    return;
  }

  if (button.dataset.panel === "results") {
    openResultsPanel();
    return;
  }

  setActiveWorkspacePanel("chat");
}


function toggleConversationHistory() {
  state.historyOpen = !state.historyOpen;

  elements.workspace?.setAttribute(
    "data-history-open",
    String(state.historyOpen),
  );

  if (!elements.toggleHistoryButton) {
    return;
  }

  const label = state.historyOpen
    ? "Thu gọn lịch sử"
    : "Mở lịch sử";

  elements.toggleHistoryButton.setAttribute(
    "aria-expanded",
    String(state.historyOpen),
  );
  elements.toggleHistoryButton.setAttribute("aria-label", label);
  elements.toggleHistoryButton.title = label;
  elements.toggleHistoryButton.querySelector("span").textContent =
    state.historyOpen ? "‹" : "☰";
}


function setActiveWorkspacePanel(panel) {
  const nextPanel = panel === "results"
    ? "results"
    : "chat";

  state.activeWorkspacePanel = nextPanel;
  elements.workspace?.setAttribute(
    "data-active-panel",
    nextPanel,
  );

  for (const button of elements.mobileTabButtons) {
    const isActive = button.dataset.panel === nextPanel;

    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  }
}


function showResultsPanelOnMobile() {
  openResultsPanel();
}


function openResultsPanel() {
  setResultsAvailability(true);
  state.resultsOpen = true;
  elements.workspace?.setAttribute("data-results-open", "true");
  elements.resultsPanel?.setAttribute("aria-hidden", "false");
  updateResultsToggleButton();

  if (window.matchMedia("(max-width: 640px)").matches) {
    setActiveWorkspacePanel("results");
  }
}


function closeResultsPanel() {
  state.resultsOpen = false;
  elements.workspace?.setAttribute("data-results-open", "false");
  elements.resultsPanel?.setAttribute("aria-hidden", "true");
  updateResultsToggleButton();

  setActiveWorkspacePanel("chat");
}


function toggleResultsPanel() {
  if (state.resultsOpen) {
    closeResultsPanel();
    return;
  }

  openResultsPanel();
}


function setResultsAvailability(isAvailable) {
  state.resultsAvailable = isAvailable;

  if (elements.toggleResultsButton) {
    elements.toggleResultsButton.hidden = !isAvailable;
  }

  if (elements.mobileResultsTab) {
    elements.mobileResultsTab.hidden = !isAvailable;
  }
}


function updateResultsToggleButton() {
  if (!elements.toggleResultsButton) {
    return;
  }

  elements.toggleResultsButton.setAttribute(
    "aria-expanded",
    String(state.resultsOpen),
  );
  elements.toggleResultsButton.classList.toggle(
    "is-active",
    state.resultsOpen,
  );

  const label = elements.toggleResultsButton.querySelector(
    ".results-toggle-label",
  );

  if (label) {
    label.textContent = state.resultsOpen
      ? "Ẩn kết quả"
      : "Xem kết quả";
  }
}


function updateMobileResultsBadge(count) {
  if (!elements.mobileResultsBadge) {
    return;
  }

  const normalizedCount = Math.max(0, Number(count) || 0);

  elements.mobileResultsBadge.hidden = normalizedCount === 0;
  elements.mobileResultsBadge.textContent =
    normalizedCount > 99 ? "99+" : String(normalizedCount);
}


async function handleSubmit(event) {
  event.preventDefault();

  const typedMessage = elements.messageInput.value.trim();
  const jobDescription = state.matchingMode
    ? elements.jobDescriptionInput.value.trim()
    : null;
  const message = typedMessage || (
    jobDescription
      ? "Hãy đánh giá mức độ phù hợp giữa CV của tôi và công việc này"
      : ""
  );

  if (!message || state.isSending) {
    return;
  }

  if (state.matchingMode && !state.uploadedCvId) {
    showError(
      "Hãy tải lên CV và chờ phân tích thành công " +
      "trước khi thực hiện yêu cầu với JD.",
    );
    return;
  }

  if (state.matchingMode && !jobDescription) {
    showError("Hãy dán Job Description cần so khớp.");
    elements.jobDescriptionInput.focus();
    return;
  }

  if (state.cvUploadStatus === "uploading") {
    showError(
      "CV đang được tải lên và xử lý. " +
      "Vui lòng chờ hoàn tất.",
    );
    return;
  }

  clearError();

  state.isSending = true;

  addMessage({
    role: "user",
    text: message,
  });

  rememberConversationThread({
    threadId: state.threadId,
    firstMessage: message,
  });

  elements.messageInput.value = "";
  resizeMessageInput();
  elements.suggestionList.hidden = true;
  updateComposerContext();

  setComposerDisabled(true);
  showTypingIndicator();

  try {
    const conversation = await sendConversationMessage({
      threadId: state.threadId,
      message,
      cvId: state.uploadedCvId,
      jobDescription,
    });

    if (conversation.threadId) {
      saveThreadId(conversation.threadId);
    }

    removeTypingIndicator();

    addMessage({
      role: "assistant",
      text: conversation.answer,
    });

    state.currentWorkflow = conversation.workflow;
    state.workflowJobMatches = conversation.workflowJobMatches;

    if (conversation.route === "job_search" && conversation.workflowJobMatches.length) {
      renderWorkflowJobRecommendations(
        conversation.jobSearchResult,
        conversation.workflowJobMatches,
        conversation.careerAdviceResult,
      );
    } else if (conversation.route === "job_search") {
      await handleJobSearchConversation(
        message,
        conversation.jobSearchResult,
      );
    }

    if (
      conversation.route === "cv_analysis" &&
      conversation.cvAnalysisResult
    ) {
      renderCvAnalysisResult(
        conversation.cvAnalysisResult,
      )
    }

    if (
      conversation.route === "cover_letter" &&
      conversation.coverLetterResult
    ) {
      renderCoverLetterResult(
        conversation.coverLetterResult,
      );
    }

    if (
      conversation.route === "career_advice" &&
      conversation.careerAdviceResult
    ) {
      renderCareerAdviceResult(conversation.careerAdviceResult);
    }

    if (
      conversation.route === "job_matching" &&
      conversation.jobMatchingResult
    ) {
      renderJobMatchingResult(
        conversation.jobMatchingResult,
      );
    }
  } catch (error) {
    removeTypingIndicator();

    const errorMessage =
      error?.message ||
      "Đã xảy ra lỗi khi xử lý yêu cầu.";

    showError(errorMessage);

    addMessage({
      role: "assistant",
      text:
        "Mình chưa thể xử lý yêu cầu này. " +
        "Bạn hãy kiểm tra backend và thử lại.",
    });
  } finally {
    state.isSending = false;
    setComposerDisabled(false);
    updateComposerContext();
    elements.messageInput.focus();
  }
}


async function handleJobSearchConversation(
  query,
  conversationSearchResult,
) {
  state.lastSearchQuery = query;
  state.currentSort = "relevance";
  elements.jobSort.value = "relevance";

  if (conversationSearchResult) {
    renderJobSearchResult(conversationSearchResult);
    return;
  }

  /*
   * Fallback:
   * Nếu Conversation Graph mới chỉ route sang job_search
   * nhưng chưa trả job_search_result, frontend gọi trực tiếp
   * endpoint /jobs/search.
   */

  showJobLoading();

  const searchResult = await searchJobs({
    query,
    sort: state.currentSort,
    page: 1,
    pageSize: 10,
  });

  renderJobSearchResult(searchResult);
}


async function handleSortChange(event) {
  const sort = event.target.value;

  if (
    !state.lastSearchQuery ||
    state.isSending
  ) {
    return;
  }

  state.currentSort = sort;
  state.isSending = true;

  clearError();
  showJobLoading();

  try {
    const result = await searchJobs({
      query: state.lastSearchQuery,
      sort,
      page: 1,
      pageSize: 10,
    });

    renderJobSearchResult(result);
  } catch (error) {
    showError(
      error?.message ||
      "Không thể sắp xếp lại kết quả.",
    );

    showJobErrorState();
  } finally {
    state.isSending = false;
  }
}


async function handleCvSelection(event) {
  const file = event.target.files?.[0];

  if (!file) {
    return;
  }

  const validationError = validateCvFile(file);

  if (validationError) {
    showError(validationError);
    elements.cvInput.value = "";
    return;
  }

  clearError();

  const requestId = state.cvUploadRequestId + 1;

  state.cvUploadRequestId = requestId;
  state.selectedCvFile = file;
  state.uploadedCvId = null;
  state.cvUploadStatus = "uploading";

  renderCvStatus();

  try {
    const result = await uploadCv(file);

    if (state.cvUploadRequestId !== requestId) {
      return;
    }

    if (!result.fileId) {
      throw new Error(
        "Backend không trả về file_id của CV.",
      );
    }

    state.uploadedCvId = result.fileId;
    state.cvUploadStatus = "uploaded";

    renderCvStatus();

    addMessage({
      role: "assistant",
      text:
        `CV “${result.fileName}” đã được tải lên ` +
        "và phân tích thành công.",
    });
  } catch (error) {
    if (state.cvUploadRequestId !== requestId) {
      return;
    }

    state.uploadedCvId = null;
    state.cvUploadStatus = "failed";

    renderCvStatus();

    showError(
      error?.message ||
      "Không thể tải CV lên backend.",
    );
  }
}


function removeCv() {
  state.cvUploadRequestId += 1;
  state.selectedCvFile = null;
  state.uploadedCvId = null;
  state.cvUploadStatus = "idle";

  elements.cvInput.value = "";

  renderCvStatus();
  clearError();
  updateComposerContext();
}


function renderCvStatus() {
  const file = state.selectedCvFile;

  if (!file) {
    elements.selectedCv.hidden = true;
    elements.cvStatusBadge.textContent = "Chưa có CV";
    elements.cvStatusBadge.className = "cv-status-badge";
    updateComposerContext();
    return;
  }

  elements.selectedCv.hidden = false;
  elements.selectedCvName.textContent = file.name;

  if (state.cvUploadStatus === "uploading") {
    elements.selectedCvStatus.textContent =
      "Đang tải lên và phân tích...";

    elements.cvStatusBadge.textContent =
      "Đang xử lý CV";

    elements.cvStatusBadge.className = "cv-status-badge is-busy";
    updateComposerContext();
    return;
  }

  if (state.cvUploadStatus === "uploaded") {
    elements.selectedCvStatus.textContent =
      "Đã tải lên và phân tích thành công";

    elements.cvStatusBadge.textContent = "CV sẵn sàng";
    elements.cvStatusBadge.className = "cv-status-badge is-ready";
    updateComposerContext();
    return;
  }

  if (state.cvUploadStatus === "failed") {
    elements.selectedCvStatus.textContent =
      "Tải lên hoặc phân tích thất bại";

    elements.cvStatusBadge.textContent = "CV bị lỗi";
    elements.cvStatusBadge.className = "cv-status-badge is-error";
    updateComposerContext();
    return;
  }

  elements.selectedCvStatus.textContent = "Đã chọn CV";
  updateComposerContext();
}


function setMatchingMode(
  enabled,
  jobDescription = "",
  matchingJob = null,
) {
  state.matchingMode = enabled;

  if (jobDescription) {
    state.jobDescription = jobDescription;
    elements.jobDescriptionInput.value = jobDescription;
  }

  elements.jobDescriptionPanel.hidden = !enabled;
  renderJobDescriptionComposerSummary(matchingJob);
  elements.toggleJdButton.classList.toggle("is-active", enabled);
  elements.toggleJdButton.setAttribute(
    "aria-pressed",
    String(enabled),
  );

  updateJobDescriptionCount();
  updateSendButton();
  updateComposerContext();

  if (enabled && !matchingJob) {
    elements.jobDescriptionInput.focus();
  }
}


function handleJobDescriptionInput(event) {
  state.jobDescription = event.target.value;
  renderJobDescriptionComposerSummary(null);
  updateJobDescriptionCount();
  updateSendButton();
}


function clearJobDescription() {
  state.jobDescription = "";
  elements.jobDescriptionInput.value = "";
  renderJobDescriptionComposerSummary(null);
  updateJobDescriptionCount();
  updateSendButton();
  elements.jobDescriptionInput.focus();
}


function updateJobDescriptionCount() {
  const length = elements.jobDescriptionInput.value.length;
  elements.jobDescriptionCount.textContent =
    `${length.toLocaleString("vi-VN")}/20.000`;
}


function handleSuggestionClick(event) {
  const coverLetterButton = event.target.closest(
    "[data-action='open-cover-letter']",
  );

  if (coverLetterButton) {
    setMatchingMode(true);

    elements.messageInput.value =
      "Hãy viết thư ứng tuyển dựa trên CV " +
      "và công việc này";

    elements.suggestionList.hidden = true;
    elements.messageInput.focus();

    resizeMessageInput();
    updateSendButton();
    return;
  }

  const matchingButton = event.target.closest(
    "[data-action='open-matching']",
  );

  if (matchingButton) {
    setMatchingMode(true);
    elements.messageInput.value =
      "Hãy đánh giá mức độ phù hợp giữa CV của tôi và công việc này";
    elements.suggestionList.hidden = true;
    resizeMessageInput();
    updateSendButton();
    return;
  }

  const button = event.target.closest("[data-message]");

  if (!button) {
    return;
  }

  elements.messageInput.value =
    button.dataset.message ?? "";

  elements.messageInput.focus();
  resizeMessageInput();
  updateSendButton();
}


function handleJobResultClick(event) {
  const coverLetterButton = event.target.closest(
    "[data-action='cover-letter-job']",
  );

  const copyCoverLetterButton = event.target.closest(
    "[data-action='copy-cover-letter']",
  );

  if (copyCoverLetterButton) {
    copyCoverLetter(copyCoverLetterButton);
    return;
  }

  const matchingButton = event.target.closest(
    "[data-action='match-job']",
  );

  const detailButton = event.target.closest(
    "[data-action='view-job']",
  );

  const actionButton =
    coverLetterButton ||
    matchingButton ||
    detailButton;

  if (!actionButton) {
    return;
  }

  const jobId = actionButton.dataset.jobId;

  if (!jobId) {
    return;
  }

  const hit = state.jobs.find(
    (item) => item?.job?.job_id === jobId,
  );

  if (!hit) {
    return;
  }

  if (matchingButton) {
    matchSelectedJob(hit);
    return;
  }

  if (coverLetterButton) {
    generateCoverLetterForJob(hit);
    return;
  }

  openJobDetail(hit);
}

async function generateCoverLetterForJob(hit) {
  const job = hit?.job ?? {};

  const description = String(
    job.description ?? "",
  ).trim();

  if (!state.uploadedCvId) {
    showError(
      "Hãy tải lên CV trước khi tạo thư ứng tuyển.",
    );
    return;
  }

  if (!description) {
    showError(
      "Công việc này chưa có JD để tạo thư ứng tuyển.",
    );
    return;
  }

  if (state.isSending) {
    return;
  }

  clearError();
  closeJobDetail();

  const message =
    `Viết thư ứng tuyển cho vị trí ${
      job.title || "này"
    }`;

  state.isSending = true;

  addMessage({
    role: "user",
    text: message,
  });

  elements.suggestionList.hidden = true;

  setComposerDisabled(true);
  showTypingIndicator();

  try {
    const conversation =
      await sendConversationMessage({
        message,
        cvId: state.uploadedCvId,
        jobDescription: description,
      });

    removeTypingIndicator();

    addMessage({
      role: "assistant",
      text: conversation.answer,
    });

    if (conversation.coverLetterResult) {
      renderCoverLetterResult(
        conversation.coverLetterResult,
      );
    }
  } catch (error) {
    removeTypingIndicator();

    showError(
      error?.message ||
        "Không thể tạo thư ứng tuyển.",
    );

    addMessage({
      role: "assistant",
      text:
        "Mình chưa thể tạo thư ứng tuyển. " +
        "Bạn hãy kiểm tra backend và thử lại.",
    });
  } finally {
    state.isSending = false;
    setComposerDisabled(false);
    updateComposerContext();
  }
}

async function matchSelectedJob(hit) {
  const job = hit?.job ?? {};
  const description = String(
    job.description ?? "",
  ).trim();

  if (!state.uploadedCvId) {
    showError(
      "Hãy tải lên CV trước khi đánh giá độ phù hợp với công việc.",
    );
    return;
  }

  if (!description) {
    showError(
      "Công việc này chưa có JD để thực hiện so khớp.",
    );
    return;
  }

  if (state.isSending) {
    return;
  }

  clearError();
  closeJobDetail();

  const message =
    `Đánh giá CV của tôi với vị trí ${job.title || "này"}`;

  state.isSending = true;

  addMessage({
    role: "user",
    text: message,
  });

  elements.messageInput.value = "";
  resizeMessageInput();
  elements.suggestionList.hidden = true;
  updateComposerContext();

  setComposerDisabled(true);
  showTypingIndicator();

  try {
    const conversation = await sendConversationMessage({
      message,
      cvId: state.uploadedCvId,
      jobDescription: description,
    });

    removeTypingIndicator();

    addMessage({
      role: "assistant",
      text: conversation.answer,
    });

    if (conversation.jobMatchingResult) {
      renderJobMatchingResult(
        conversation.jobMatchingResult,
      );
    }
  } catch (error) {
    removeTypingIndicator();

    showError(
      error?.message ||
      "Không thể so khớp CV với công việc này.",
    );

    addMessage({
      role: "assistant",
      text:
        "Mình chưa thể so khớp CV với công việc này. " +
        "Bạn hãy kiểm tra backend và thử lại.",
    });
  } finally {
    state.isSending = false;
    setComposerDisabled(false);
    updateComposerContext();
  }
}

function renderWorkflowJobRecommendations(
  searchResult,
  matches,
  careerAdvice,
) {
  const normalizedMatches =
    Array.isArray(matches)
      ? matches
      : [];

  state.currentSearchResult = searchResult;
  state.workflowJobMatches =
    normalizedMatches;

  state.jobs = normalizedMatches.map(
    (item) => ({
      job: item.job,
      workflowMatch: item.match,
    }),
  );

  elements.resultsEyebrow.textContent =
    "AI JOB RECOMMENDATION";

  elements.resultsTitle.textContent =
    "Công việc phù hợp nhất";

  elements.resultsSummary.hidden = false;
  elements.jobSort.disabled = true;
  elements.backToJobsButton.hidden = true;

  elements.resultCount.textContent =
    `${normalizedMatches.length} công việc phù hợp nhất với CV`;

  elements.searchStrategy.textContent =
    "Multi-Agent Matching";

  updateMobileResultsBadge(
    normalizedMatches.length,
  );

  showResultsPanelOnMobile();

  if (!normalizedMatches.length) {
    showNoJobResults();
    return;
  }

  elements.jobResults.innerHTML = `
    <section
      class="workflow-recommendations"
      aria-label="Danh sách công việc phù hợp"
    >
      ${normalizedMatches
        .map(
          (item, index) =>
            renderWorkflowJobCard(
              item,
              index,
            ),
        )
        .join("")}

      ${
        careerAdvice
          ? renderWorkflowCareerSummary(
              careerAdvice,
            )
          : ""
      }
    </section>
  `;
}

function renderWorkflowJobCard(
  item,
  index,
) {
  const job = item?.job ?? {};
  const match = item?.match ?? {};

  const score = clampMatchingScore(
    match.overallScore,
  );

  const title =
    job.title ||
    "Vị trí chưa xác định";

  const company =
    job.company ||
    "Chưa rõ công ty";

  const location =
    job.location ||
    "Chưa rõ địa điểm";

  const strengths =
    Array.isArray(match.strengths)
      ? match.strengths.slice(0, 3)
      : [];

  const gaps =
    Array.isArray(match.gaps)
      ? match.gaps.slice(0, 3)
      : [];

  return `
    <article class="workflow-job-card">
      <header class="workflow-job-header">
        <div class="workflow-job-rank">
          #${index + 1}
        </div>

        <div class="workflow-job-title">
          <h3>${escapeHtml(title)}</h3>

          <p>
            ${escapeHtml(company)}
            ·
            ${escapeHtml(location)}
          </p>
        </div>

        <div class="workflow-match-score">
          <strong>
            ${score.toFixed(1)}
          </strong>
          <span>/100</span>
        </div>
      </header>

      <div class="workflow-match-meta">
        <span class="recommendation-badge">
          ${escapeHtml(
            getRecommendationLabel(
              match.recommendation,
            ),
          )}
        </span>
      </div>

      <div class="workflow-match-columns">
        <section>
          <h4>Điểm mạnh</h4>

          ${
            strengths.length
              ? `
                <ul>
                  ${strengths
                    .map(
                      (strength) =>
                        `<li>${escapeHtml(
                          strength,
                        )}</li>`,
                    )
                    .join("")}
                </ul>
              `
              : "<p>Chưa có dữ liệu.</p>"
          }
        </section>

        <section>
          <h4>Khoảng trống</h4>

          ${
            gaps.length
              ? `
                <ul>
                  ${gaps
                    .map(
                      (gap) =>
                        `<li>${escapeHtml(
                          gap,
                        )}</li>`,
                    )
                    .join("")}
                </ul>
              `
              : "<p>Chưa có khoảng trống đáng kể.</p>"
          }
        </section>
      </div>

      <div class="workflow-job-actions">
        <button
          type="button"
          class="secondary-button"
          data-action="view-job"
          data-job-id="${escapeHtml(
            job.job_id ?? "",
          )}"
        >
          Xem công việc
        </button>

        <button
          type="button"
          class="primary-button"
          data-action="cover-letter-job"
          data-job-id="${escapeHtml(
            job.job_id ?? "",
          )}"
        >
          Viết Cover Letter
        </button>
      </div>
    </article>
  `;
}

function renderWorkflowCareerSummary(
  advice,
) {
  const skills =
    Array.isArray(advice.topPrioritySkills)
      ? advice.topPrioritySkills
      : [];

  return `
    <section class="workflow-career-summary">
      <span class="career-personalization-badge personalized">
        Career Advisor
      </span>

      <h3>
        Bạn nên cải thiện gì tiếp theo?
      </h3>

      <p>
        ${escapeHtml(
          advice.summary ||
          "Chưa có nhận xét.",
        )}
      </p>

      ${
        skills.length
          ? `
            <div class="career-skill-chips">
              ${skills
                .map(
                  (skill) =>
                    `<span>${escapeHtml(
                      skill,
                    )}</span>`,
                )
                .join("")}
            </div>
          `
          : ""
      }
    </section>
  `;
}

function renderJobSearchResult(result) {
  const items = Array.isArray(result?.items)
    ? result.items
    : [];

  state.currentSearchResult = result;
  state.jobs = items;
  state.currentMatchingResult = null;

  elements.resultsSummary.hidden = false;
  elements.jobSort.disabled = false;
  elements.backToJobsButton.hidden = true;

  const total = Number.isFinite(Number(result?.total))
    ? Number(result.total)
    : items.length;

  elements.resultCount.textContent =
    `Đang hiển thị ${items.length}/${total} công việc được đề xuất`;

  elements.searchStrategy.textContent = getStrategyLabel(result.strategy);
  updateMobileResultsBadge(total);
  showResultsPanelOnMobile();

  renderMatchedTermChips(items);

  if (items.length === 0) {
    showNoJobResults();
    return;
  }

  elements.jobResults.innerHTML = items.map(renderJobCard).join("");
}

function renderCoverLetterResult(result) {
  state.currentCoverLetterResult = result;
  state.currentMatchingResult = null;
  state.currentCvAnalysisResult = null;
  state.currentCareerAdviceResult = null;

  elements.resultsEyebrow.textContent =
    "COVER LETTER";

  elements.resultsTitle.textContent =
    "Thư ứng tuyển";

  elements.resultsSummary.hidden = true;
  elements.jobSort.disabled = true;

  elements.backToJobsButton.hidden =
    !state.currentSearchResult ||
    !state.jobs.length;

  const confidence =
    result.confidence === null
      ? "Chưa xác định"
      : `${Math.round(
          result.confidence * 100,
        )}%`;

  elements.jobResults.innerHTML = `
    <section
      class="cover-letter-result"
      aria-label="Thư ứng tuyển"
    >
      <header class="cover-letter-header">
        <div>
          <span class="cover-letter-badge">
            ${escapeHtml(
              getCoverLetterLanguageLabel(
                result.language,
              ),
            )}
          </span>

          <span
            class="cover-letter-badge secondary"
          >
            ${escapeHtml(
              getCoverLetterToneLabel(
                result.tone,
              ),
            )}
          </span>
        </div>

        <button
          type="button"
          class="primary-button"
          data-action="copy-cover-letter"
        >
          Sao chép thư
        </button>
      </header>

      <article class="cover-letter-paper">
        <pre>${escapeHtml(
          result.fullText,
        )}</pre>
      </article>

      <div class="cover-letter-meta">
        <span>
          ${escapeHtml(result.wordCount)} từ
        </span>

        <span>
          Độ tin cậy:
          ${escapeHtml(confidence)}
        </span>

        <span>
          ${
            result.isPersonalized
              ? "Cá nhân hóa theo CV"
              : "Bản tổng quát"
          }
        </span>
      </div>

      <div class="cover-letter-evidence-grid">
        ${renderCoverLetterEvidence(
          "Bằng chứng CV đã sử dụng",
          result.cvEvidenceUsed,
        )}

        ${renderCoverLetterEvidence(
          "Yêu cầu công việc đã đề cập",
          result.jobRequirementsAddressed,
        )}
      </div>
    </section>
  `;

  updateMobileResultsBadge(1);
  showResultsPanelOnMobile();
}


function renderCoverLetterEvidence(
  title,
  items,
) {
  return `
    <section class="cover-letter-evidence">
      <h3>${escapeHtml(title)}</h3>

      ${
        items?.length
          ? `
            <ul>
              ${items
                .map(
                  (item) =>
                    `<li>${escapeHtml(item)}</li>`,
                )
                .join("")}
            </ul>
          `
          : "<p>Chưa có dữ liệu.</p>"
      }
    </section>
  `;
}


async function copyCoverLetter(button) {
  const fullText =
    state.currentCoverLetterResult?.fullText;

  if (!fullText) {
    showError(
      "Không có nội dung thư để sao chép.",
    );
    return;
  }

  try {
    await navigator.clipboard.writeText(
      fullText,
    );

    const originalText = button.textContent;

    button.textContent = "Đã sao chép";

    setTimeout(() => {
      button.textContent = originalText;
    }, 1800);
  } catch {
    showError(
      "Trình duyệt không cho phép sao chép tự động.",
    );
  }
}


function getCoverLetterLanguageLabel(
  language,
) {
  return language === "en"
    ? "English"
    : "Tiếng Việt";
}


function getCoverLetterToneLabel(tone) {
  const labels = {
    professional: "Chuyên nghiệp",
    confident: "Tự tin",
    enthusiastic: "Nhiệt huyết",
  };

  return labels[tone] ?? "Chuyên nghiệp";
}

function renderCareerAdviceResult(result) {
  state.currentCareerAdviceResult = result;
  state.currentCvAnalysisResult = null;
  state.currentMatchingResult = null;

  elements.resultsEyebrow.textContent = "CAREER ADVICE";
  elements.resultsTitle.textContent = "Định hướng nghề nghiệp";

  if (elements.resultsSummary) {
    elements.resultsSummary.hidden = true;
  }

  const confidence =
    result.confidence === null
      ? "Chưa xác định"
      : `${Math.round(result.confidence * 100)}%`;

  elements.jobResults.innerHTML = `
    <section
      class="career-advice-result"
      aria-label="Kết quả tư vấn nghề nghiệp"
    >
      <header class="career-advice-overview">
        <span class="career-personalization-badge ${
          result.isPersonalized ? "personalized" : "general"
        }">
          ${
            result.isPersonalized
              ? "Cá nhân hóa theo CV"
              : "Tư vấn tổng quát"
          }
        </span>

        <h3>${escapeHtml(
          result.careerGoal || "Định hướng nghề nghiệp"
        )}</h3>

        <p>${escapeHtml(result.summary)}</p>

        <span class="career-confidence">
          Độ tin cậy: ${escapeHtml(confidence)}
        </span>
      </header>

      ${renderTopPrioritySkills(result.topPrioritySkills)}
      ${renderCareerRoles(result.recommendedRoles)}
      ${renderCareerSkillGaps(result.skillGaps)}
      ${renderCareerRoadmap(result.roadmap)}
      ${renderPortfolioProjects(result.portfolioProjects)}
      ${renderCareerNextActions(result.nextActions)}
    </section>
  `;

  updateMobileResultsBadge(1);
  showResultsPanelOnMobile();
}

function renderTopPrioritySkills(skills) {
  if (!skills.length) {
    return "";
  }

  return `
    <section class="career-section">
      <h3>Kỹ năng cần ưu tiên</h3>

      <div class="career-skill-chips">
        ${skills
          .map(
            (skill) => `
              <span>${escapeHtml(skill)}</span>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderCareerRoles(roles) {
  if (!roles.length) {
    return "";
  }

  return `
    <section class="career-section">
      <h3>Vị trí nghề nghiệp phù hợp</h3>

      <div class="career-role-grid">
        ${roles
          .map(
            (role) => `
              <article class="career-role-card">
                <div class="career-card-header">
                  <h4>${escapeHtml(role.roleTitle)}</h4>

                  <span class="readiness-badge ${escapeHtml(
                    role.readinessLevel
                  )}">
                    ${escapeHtml(
                      getCareerReadinessLabel(role.readinessLevel)
                    )}
                  </span>
                </div>

                <p>${escapeHtml(role.rationale)}</p>

                ${renderCareerList(
                  "Bằng chứng từ CV",
                  role.cvEvidence
                )}

                ${renderCareerList(
                  "Điểm cần phát triển",
                  role.developmentNeeds
                )}
              </article>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderCareerSkillGaps(skillGaps) {
  if (!skillGaps.length) {
    return "";
  }

  return `
    <section class="career-section">
      <h3>Khoảng trống kỹ năng</h3>

      <div class="career-gap-list">
        ${skillGaps
          .map(
            (gap) => `
              <article class="career-gap-card">
                <div class="career-card-header">
                  <h4>${escapeHtml(gap.skill)}</h4>

                  <span class="career-priority priority-${escapeHtml(
                    gap.priority
                  )}">
                    ${escapeHtml(
                      getImprovementPriorityLabel(gap.priority)
                    )}
                  </span>
                </div>

                <p>${escapeHtml(gap.reason)}</p>

                ${renderCareerList(
                  "Nền tảng hiện tại",
                  gap.currentEvidence
                )}

                <div class="career-action-box">
                  <strong>Hành động đề xuất</strong>
                  <p>${escapeHtml(gap.recommendedAction)}</p>
                </div>
              </article>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderCareerRoadmap(roadmap) {
  if (!roadmap.length) {
    return "";
  }

  return `
    <section class="career-section">
      <h3>Lộ trình phát triển</h3>

      <div class="career-roadmap">
        ${roadmap
          .map(
            (step) => `
              <article class="career-roadmap-step">
                <div class="career-phase">${escapeHtml(step.phase)}</div>

                <div class="career-roadmap-content">
                  <div class="career-card-header">
                    <h4>${escapeHtml(step.title)}</h4>
                    <span>${escapeHtml(step.timeframe)}</span>
                  </div>

                  <p>${escapeHtml(step.objective)}</p>

                  ${renderCareerList("Hành động", step.actions)}

                  ${renderCareerList(
                    "Tiêu chí hoàn thành",
                    step.successCriteria
                  )}
                </div>
              </article>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderPortfolioProjects(projects) {
  if (!projects.length) {
    return "";
  }

  return `
    <section class="career-section">
      <h3>Dự án portfolio đề xuất</h3>

      <div class="career-project-grid">
        ${projects
          .map(
            (project) => `
              <article class="career-project-card">
                <h4>${escapeHtml(project.title)}</h4>
                <p>${escapeHtml(project.purpose)}</p>

                ${renderCareerList(
                  "Kỹ năng thực hành",
                  project.skillsPracticed
                )}

                ${renderCareerList(
                  "Tính năng gợi ý",
                  project.suggestedFeatures
                )}

                <div class="career-action-box">
                  <strong>Kết quả đầu ra</strong>
                  <p>${escapeHtml(project.expectedDeliverable)}</p>
                </div>
              </article>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderCareerNextActions(actions) {
  if (!actions.length) {
    return "";
  }

  return `
    <section class="career-section">
      <h3>Việc nên làm tiếp theo</h3>

      <div class="career-next-actions">
        ${actions
          .map(
            (item) => `
              <article class="career-next-action">
                <span class="career-priority priority-${escapeHtml(
                  item.priority
                )}">
                  ${escapeHtml(
                    getImprovementPriorityLabel(item.priority)
                  )}
                </span>

                <div>
                  <h4>${escapeHtml(item.action)}</h4>
                  <p>${escapeHtml(item.reason)}</p>

                  ${
                    item.timeframe
                      ? `<small>Thời gian: ${escapeHtml(
                          item.timeframe
                        )}</small>`
                      : ""
                  }
                </div>
              </article>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderCareerList(title, items) {
  if (!items?.length) {
    return "";
  }

  return `
    <div class="career-list">
      <strong>${escapeHtml(title)}</strong>

      <ul>
        ${items
          .map((item) => `<li>${escapeHtml(item)}</li>`)
          .join("")}
      </ul>
    </div>
  `;
}

function getCareerReadinessLabel(value) {
  const labels = {
    ready: "Sẵn sàng",
    nearly_ready: "Gần sẵn sàng",
    developing: "Đang phát triển",
    exploring: "Đang khám phá",
  };

  return labels[value] ?? "Chưa xác định";
}

function renderCvAnalysisResult(result) {
  state.currentCvAnalysisResult = result;
  state.currentMatchingResult = null;

  const score = clampMatchingScore(result?.overallScore);
  const breakdown = result?.breakdown ?? {};
  const strengths = Array.isArray(result?.strengths)
    ? result.strengths : [];

  const weaknesses = Array.isArray(result?.weaknesses)
    ? result.weaknesses : [];

  const improvements = Array.isArray(result?.improvements)
    ? result.improvements : [];

  const qualityLevel = result?.qualityLevel ?? "needs_improvement";

  elements.resultsEyebrow.textContent = "CV ANALYSIS";
  elements.resultsTitle.textContent = "Phân tích CV";
  elements.resultsSummary.hidden = true;
  elements.jobSort.disabled = true;

  elements.backToJobsButton.hidden =
    !state.currentSearchResult ||
    !state.jobs.length;

  updateMobileResultsBadge(1);
  showResultsPanelOnMobile();

  elements.jobResults.innerHTML = `
    <section
      class="matching-result cv-analysis-result"
      aria-label="Kết quả phân tích CV"
    >
      <header class="matching-overview">
        <div
          class="matching-score-ring"
          style="--matching-score: ${score}"
          aria-label="Điểm chất lượng CV ${score.toFixed(2)} trên 100"
        >
          <strong>${score.toFixed(2)}</strong>
          <span>/100</span>
        </div>

        <div class="matching-summary">
          <span
            class="recommendation-badge ${getCvQualityBadgeClass(
              qualityLevel,
            )}"
          >
            ${escapeHtml(
              getCvQualityLabel(qualityLevel),
            )}
          </span>

          <h3>Chất lượng nội dung CV</h3>

          <p>
            ${escapeHtml(
              result?.summary ||
                "Chưa có nhận xét tổng quan.",
            )}
          </p>

          ${
            result?.confidence === null ||
            result?.confidence === undefined
              ? ""
              : `
                <small>
                  Độ tin cậy đánh giá:
                  ${Math.round(
                    result.confidence * 100,
                  )}%
                </small>
              `
          }
        </div>
      </header>

      <section class="matching-section">
        <h3>Điểm thành phần</h3>

        <div class="breakdown-grid">
          ${renderBreakdownItem(
            "Độ đầy đủ",
            breakdown.completeness,
          )}

          ${renderBreakdownItem(
            "Giới thiệu bản thân",
            breakdown.professionalSummary,
          )}

          ${renderBreakdownItem(
            "Kỹ năng",
            breakdown.skills,
          )}

          ${renderBreakdownItem(
            "Kinh nghiệm",
            breakdown.workExperience,
          )}

          ${renderBreakdownItem(
            "Dự án",
            breakdown.projects,
          )}

          ${renderBreakdownItem(
            "Học vấn & chứng chỉ",
            breakdown.educationAndCredentials,
          )}
        </div>
      </section>

      <div class="matching-columns">
        ${renderCvFindingList(
          "Điểm mạnh",
          strengths,
          "strength",
          "Chưa xác định được điểm mạnh nổi bật.",
        )}

        ${renderCvFindingList(
          "Điểm cần cải thiện",
          weaknesses,
          "gap",
          "Chưa ghi nhận điểm yếu quan trọng.",
        )}
      </div>

      <section class="matching-section cv-improvements">
        <h3>Đề xuất cải thiện</h3>

        ${
          improvements.length
            ? `
              <div class="cv-improvement-list">
                ${improvements
                  .map(renderCvImprovement)
                  .join("")}
              </div>
            `
            : `
              <p class="matching-empty-text">
                Chưa có đề xuất cải thiện.
              </p>
            `
        }
      </section>
    </section>
  `;
}

function renderCvFindingList(
  title,
  items,
  variant,
  emptyMessage,
) {
  return `
    <section
      class="matching-list-card ${escapeHtml(variant)}"
    >
      <h3>${escapeHtml(title)}</h3>

      ${
        items.length
          ? `
            <ul class="cv-finding-list">
              ${items
                .map((item) => {
                  const evidence = Array.isArray(
                    item?.cvEvidence,
                  )
                    ? item.cvEvidence
                    : [];

                  return `
                    <li>
                      <strong>
                        ${escapeHtml(
                          item?.finding ||
                            "Chưa có nhận xét.",
                        )}
                      </strong>

                      <span class="cv-section-label">
                        ${escapeHtml(
                          getCvSectionLabel(
                            item?.section,
                          ),
                        )}
                      </span>

                      ${
                        evidence.length
                          ? `
                            <ul class="cv-finding-evidence">
                              ${evidence
                                .map(
                                  (value) => `
                                    <li>
                                      ${escapeHtml(value)}
                                    </li>
                                  `,
                                )
                                .join("")}
                            </ul>
                          `
                          : ""
                      }
                    </li>
                  `;
                })
                .join("")}
            </ul>
          `
          : `<p>${escapeHtml(emptyMessage)}</p>`
      }
    </section>
  `;
}

function renderCvImprovement(item) {
  const priority = item?.priority ?? "medium";

  return `
    <article
      class="cv-improvement-item priority-${escapeHtml(
        priority,
      )}"
    >
      <header>
        <span
          class="cv-priority-badge ${escapeHtml(
            priority,
          )}"
        >
          ${escapeHtml(
            getImprovementPriorityLabel(priority),
          )}
        </span>

        <span class="cv-section-label">
          ${escapeHtml(
            getCvSectionLabel(item?.section),
          )}
        </span>
      </header>

      <h4>
        ${escapeHtml(
          item?.issue || "Nội dung cần cải thiện",
        )}
      </h4>

      <p>
        ${escapeHtml(
          item?.suggestion ||
            "Chưa có hướng dẫn cụ thể.",
        )}
      </p>

      ${
        item?.example
          ? `
            <div class="cv-improvement-example">
              <strong>Ví dụ tham khảo</strong>
              <p>${escapeHtml(item.example)}</p>
            </div>
          `
          : ""
      }
    </article>
  `;
}

function renderJobMatchingResult(result) {
  state.currentMatchingResult = result;
  const score = clampMatchingScore(result?.overallScore);
  const breakdown = result?.breakdown ?? {};
  const strengths = Array.isArray(result?.strengths)
    ? result.strengths
    : [];
  const gaps = Array.isArray(result?.gaps)
    ? result.gaps
    : [];
  const evidence = Array.isArray(result?.evidence)
    ? result.evidence
    : [];
  const actionPlan = createMatchingActionPlan({
    score,
    gaps,
    evidence,
    recommendation: result?.recommendation,
  });

  elements.resultsEyebrow.textContent = "CV · JOB MATCHING";
  elements.resultsTitle.textContent = "Kết quả so khớp";
  elements.resultsSummary.hidden = true;
  elements.jobSort.disabled = true;
  elements.backToJobsButton.hidden =
    !state.currentSearchResult ||
    !state.jobs.length;
  updateMobileResultsBadge(1);
  showResultsPanelOnMobile();

  elements.jobResults.innerHTML = `
    <section class="matching-result" aria-label="Kết quả so khớp CV">
      <header class="matching-overview">
        <div
          class="matching-score-ring"
          style="--matching-score: ${score}"
          aria-label="Điểm phù hợp ${score.toFixed(2)} trên 100"
        >
          <strong>${score.toFixed(2)}</strong>
          <span>/100</span>
        </div>

        <div class="matching-summary">
          <span class="recommendation-badge ${escapeHtml(
            result?.recommendation || "low_match",
          )}">
            ${escapeHtml(
              getRecommendationLabel(result?.recommendation),
            )}
          </span>

          <h3>Mức độ phù hợp tổng thể</h3>
          <p>${escapeHtml(result?.summary || "Chưa có nhận xét tổng quan.")}</p>

          ${
            result?.confidence === null ||
            result?.confidence === undefined
              ? ""
              : `
                <small>
                  Độ tin cậy đánh giá:
                  ${Math.round(result.confidence * 100)}%
                </small>
              `
          }
        </div>
      </header>

      <section class="matching-section action-plan">
        <div>
          <span class="section-kicker">Hành động tiếp theo</span>
          <h3>Ưu tiên trước khi ứng tuyển</h3>
        </div>

        <ol>
          ${actionPlan
            .map((item) => `<li>${escapeHtml(item)}</li>`)
            .join("")}
        </ol>
      </section>

      <section class="matching-section">
        <h3>Điểm thành phần</h3>
        <div class="breakdown-grid">
          ${renderBreakdownItem(
            "Kỹ năng chuyên môn",
            breakdown.technicalSkills,
          )}
          ${renderBreakdownItem(
            "Kinh nghiệm",
            breakdown.experience,
          )}
          ${renderBreakdownItem(
            "Dự án",
            breakdown.projects,
          )}
          ${renderBreakdownItem(
            "Học vấn",
            breakdown.education,
          )}
          ${renderBreakdownItem(
            "Ngoại ngữ & chứng chỉ",
            breakdown.languagesAndCertifications,
          )}
        </div>
      </section>

      <div class="matching-columns">
        ${renderMatchingList(
          "Điểm mạnh",
          strengths,
          "strength",
          "Chưa xác định được điểm mạnh nổi bật.",
        )}
        ${renderMatchingList(
          "Khoảng thiếu",
          gaps,
          "gap",
          "Không có khoảng thiếu quan trọng được ghi nhận.",
        )}
      </div>

      <section class="matching-section evidence-section">
        <h3>Bằng chứng đánh giá</h3>
        ${
          evidence.length
            ? `<div class="evidence-list">
                ${evidence.map(renderEvidenceItem).join("")}
              </div>`
            : `<p class="matching-empty-text">
                Chưa có bằng chứng chi tiết.
              </p>`
        }
      </section>
    </section>
  `;
}


function showJobSearchResultsFromState() {
  if (!state.currentSearchResult) {
    showInitialJobState();
    return;
  }

  renderJobSearchResult(state.currentSearchResult);
  showResultsPanelOnMobile();
}


function renderBreakdownItem(label, value) {
  const score = clampMatchingScore(value);

  return `
    <article class="breakdown-item">
      <div>
        <span>${escapeHtml(label)}</span>
        <strong>${score.toFixed(0)}</strong>
      </div>
      <div class="score-track" aria-hidden="true">
        <span style="width: ${score}%"></span>
      </div>
    </article>
  `;
}


function createMatchingActionPlan({
  score,
  gaps,
  evidence,
  recommendation,
}) {
  const missingEvidence = evidence
    .filter((item) => item?.status === "missing")
    .map((item) => item.requirement)
    .filter(Boolean);

  const plan = [];

  if (score >= 80 || recommendation === "strong_match") {
    plan.push(
      "Chuẩn bị nộp hồ sơ, ưu tiên làm nổi bật các điểm mạnh đang khớp với JD.",
    );
  } else if (score >= 60) {
    plan.push(
      "Ứng tuyển được, nhưng nên chỉnh CV để nhấn mạnh kinh nghiệm gần nhất với vai trò.",
    );
  } else {
    plan.push(
      "Khoan ứng tuyển ngay; hãy bổ sung bằng chứng kỹ năng trước để tăng tỷ lệ phản hồi.",
    );
  }

  if (missingEvidence.length) {
    plan.push(
      `Bổ sung ví dụ cụ thể cho: ${missingEvidence.slice(0, 2).join(", ")}.`,
    );
  } else if (gaps.length) {
    plan.push(
      `Xử lý khoảng thiếu nổi bật: ${gaps.slice(0, 2).join(", ")}.`,
    );
  } else {
    plan.push(
      "Giữ CV ngắn gọn và dùng từ khóa giống JD ở phần kinh nghiệm gần nhất.",
    );
  }

  plan.push(
    "Chuẩn bị 2-3 câu chuyện phỏng vấn có số liệu, vai trò cá nhân và kết quả rõ ràng.",
  );

  return plan;
}


function renderMatchingList(
  title,
  items,
  variant,
  emptyMessage,
) {
  return `
    <section class="matching-list-card ${escapeHtml(variant)}">
      <h3>${escapeHtml(title)}</h3>
      ${
        items.length
          ? `<ul>
              ${items
                .map((item) => `<li>${escapeHtml(item)}</li>`)
                .join("")}
            </ul>`
          : `<p>${escapeHtml(emptyMessage)}</p>`
      }
    </section>
  `;
}


function renderEvidenceItem(item) {
  const cvEvidence = Array.isArray(item?.cvEvidence)
    ? item.cvEvidence
    : [];

  return `
    <details class="evidence-item">
      <summary>
        <span class="evidence-status ${escapeHtml(item?.status || "missing")}">
          ${escapeHtml(getEvidenceStatusLabel(item?.status))}
        </span>
        <span>${escapeHtml(item?.requirement || "Yêu cầu công việc")}</span>
      </summary>

      <div class="evidence-content">
        <p>${escapeHtml(item?.explanation || "Chưa có giải thích.")}</p>

        ${
          cvEvidence.length
            ? `<strong>Bằng chứng từ CV</strong>
              <ul>
                ${cvEvidence
                  .map((evidence) => `<li>${escapeHtml(evidence)}</li>`)
                  .join("")}
              </ul>`
            : `<span class="no-cv-evidence">
                Không tìm thấy bằng chứng tương ứng trong CV.
              </span>`
        }
      </div>
    </details>
  `;
}


function renderMatchedTermChips(items) {
  const matchedTerms = [
    ...new Set(
      items.flatMap((item) =>
        Array.isArray(item.matchedTerms)
          ? item.matchedTerms
          : [],
      ),
    ),
  ].slice(0, 6);

  elements.activeFilters.innerHTML = "";

  for (const term of matchedTerms) {
    const chip = document.createElement("span");

    chip.className = "filter-chip";
    chip.textContent = term;

    elements.activeFilters.append(chip);
  }
}


function renderJobCard(hit) {
  const job = hit?.job ?? {};
  const score = hit?.score ?? {};
  const reasons = Array.isArray(hit?.reasons)
    ? hit.reasons.slice(0, 3)
    : [];

  const skills = Array.isArray(job.skills)
    ? job.skills.slice(0, 7)
    : [];

  const jobId = String(job.job_id ?? "");
  const sourceUrl = safeExternalUrl(job.source_url);
  const matchPercentage = formatScore(score.final);
  const matchTone = getMatchTone(score.final);

  const salary = formatSalary(job);

  return `
    <article class="job-card">
      <header class="job-card-header">
        <div class="job-heading">
          <h3 class="job-title">
            ${escapeHtml(job.title || "Chưa có chức danh")}
          </h3>

          <span class="job-company">
            ${escapeHtml(job.company || "Chưa có công ty")}
          </span>
        </div>

        <div class="match-score ${matchTone}">
          <strong>${matchPercentage}</strong>
          <small>${escapeHtml(getMatchLabel(score.final))}</small>
        </div>
      </header>

      <div class="job-meta job-meta-priority">
        ${
          salary
            ? renderMetaItem("Lương", salary)
            : ""
        }

        ${renderMetaItem(
          "Địa điểm",
          job.location || "Không xác định",
        )}

        ${renderMetaItem(
          "Cấp độ",
          getSeniorityLabel(job.seniority_level),
        )}

        ${renderMetaItem(
          "Hình thức",
          getWorkModeLabel(job.work_mode),
        )}

        ${renderMetaItem(
          "Loại việc",
          getEmploymentTypeLabel(job.employment_type),
        )}

      </div>

      ${
        skills.length
          ? `
            <div class="skill-list">
              ${skills
                .map(
                  (skill) => `
                    <span class="skill-chip">
                      ${escapeHtml(skill)}
                    </span>
                  `,
                )
                .join("")}
            </div>
          `
          : ""
      }

      ${
        reasons.length
          ? `
            <div class="reason-block">
              <strong>Vì sao nên xem?</strong>
              <ul class="reason-list">
              ${reasons
                .map(
                  (reason) => `
                    <li>${escapeHtml(reason)}</li>
                  `,
                )
                .join("")}
              </ul>
            </div>
          `
          : ""
      }

      <footer class="job-card-actions">
        <button
          type="button"
          class="ghost-button"
          data-action="view-job"
          data-job-id="${escapeHtml(jobId)}"
        >
          Xem chi tiết
        </button>

        <button
          type="button"
          class="primary-button"
          data-action="match-job"
          data-job-id="${escapeHtml(jobId)}"
        >
          So khớp CV
        </button>

        ${
          sourceUrl
            ? `
              <a
                class="primary-button"
                href="${escapeHtml(sourceUrl)}"
                target="_blank"
                rel="noopener noreferrer"
              >
                Ứng tuyển
              </a>
            `
            : ""
        }

        <button
          type="button"
          class="ghost-button"
          data-action="cover-letter-job"
          data-job-id="${escapeHtml(jobId)}"
        >
          Viết thư
        </button>

      </footer>
    </article>
  `;
}


function renderMetaItem(label, value) {
  if (!value) {
    return "";
  }

  return `
    <span class="job-meta-item ${label === "Lương" ? "is-salary" : ""}">
      <span class="job-meta-label">
        ${escapeHtml(label)}:
      </span>

      ${escapeHtml(value)}
    </span>
  `;
}


function getMatchTone(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "is-low";
  }

  if (number >= 0.78) {
    return "is-strong";
  }

  if (number >= 0.58) {
    return "is-good";
  }

  return "is-low";
}


function getMatchLabel(value) {
  const tone = getMatchTone(value);

  if (tone === "is-strong") {
    return "rất khớp";
  }

  if (tone === "is-good") {
    return "đáng xem";
  }

  return "cần lọc";
}


function openJobDetail(hit) {
  const job = hit?.job ?? {};
  const sourceUrl = safeExternalUrl(job.source_url);

  state.selectedJob = hit;
  state.lastFocusedBeforeDrawer = document.activeElement;

  elements.jobDetailContent.innerHTML = `
    <section class="drawer-job-heading">
      <h2>${escapeHtml(job.title || "Công việc")}</h2>
      <p>${escapeHtml(job.company || "Chưa có công ty")}</p>
    </section>

    <div class="job-meta">
      ${renderMetaItem(
        "Địa điểm",
        job.location || "Không xác định",
      )}

      ${renderMetaItem(
        "Cấp độ",
        getSeniorityLabel(job.seniority_level),
      )}

      ${renderMetaItem(
        "Hình thức",
        getWorkModeLabel(job.work_mode),
      )}

      ${renderMetaItem(
        "Loại việc",
        getEmploymentTypeLabel(job.employment_type),
      )}

      ${renderMetaItem(
        "Ngày đăng",
        formatDate(job.posted_at),
      )}

      ${renderMetaItem(
        "Nguồn",
        job.source || "Không xác định",
      )}
    </div>

    ${
      Array.isArray(job.skills) && job.skills.length
        ? `
          <section class="drawer-section">
            <h3>Kỹ năng</h3>

            <div class="skill-list">
              ${job.skills
                .map(
                  (skill) => `
                    <span class="skill-chip">
                      ${escapeHtml(skill)}
                    </span>
                  `,
                )
                .join("")}
            </div>
          </section>
        `
        : ""
    }

    ${
      Array.isArray(hit.reasons) && hit.reasons.length
        ? `
          <section class="drawer-section">
            <h3>Vì sao công việc này phù hợp?</h3>

            <ul class="reason-list">
              ${hit.reasons
                .map(
                  (reason) => `
                    <li>${escapeHtml(reason)}</li>
                  `,
                )
                .join("")}
            </ul>
          </section>
        `
        : ""
    }

    <section class="drawer-section">
      <h3>Chi tiết JD</h3>

      ${renderJobDescription(job.description)}
    </section>

    <div class="drawer-actions">
      <button
        type="button"
        class="primary-button"
        id="match-drawer-job"
      >
        So khớp với CV
      </button>

      ${
        sourceUrl
          ? `
            <a
              class="primary-button"
              href="${escapeHtml(sourceUrl)}"
              target="_blank"
              rel="noopener noreferrer"
            >
              Đi đến trang ứng tuyển
            </a>
          `
          : ""
      }

      <button
        type="button"
        class="ghost-button"
        id="close-drawer-action"
      >
        Đóng
      </button>

      <button
        type="button"
        class="ghost-button"
        id="cover-letter-drawer-job"
      >
        Viết thư ứng tuyển
      </button>

    </div>
  `;

  elements.jobDetailContent
  .querySelector("#cover-letter-drawer-job",)
  ?.addEventListener(
    "click",
    () => generateCoverLetterForJob(hit),
  );

  elements.jobDetailContent
    .querySelector("#match-drawer-job")
    ?.addEventListener(
      "click",
      () => matchSelectedJob(hit),
    );

  elements.jobDetailContent
    .querySelector("#close-drawer-action")
    ?.addEventListener(
      "click",
      closeJobDetail,
    );

  elements.jobDetailOverlay.hidden = false;

  elements.jobDetailDrawer.classList.add("is-open");
  elements.jobDetailDrawer.setAttribute(
    "aria-hidden",
    "false",
  );

  requestAnimationFrame(() => {
    elements.closeJobDetailButton.focus();
  });
}


function renderJobDescription(description) {
  const sections = parseJobDescriptionSections(description);

  if (!sections.length) {
    return `
      <p class="job-description-empty">
        Công việc chưa có mô tả chi tiết.
      </p>
    `;
  }

  return `
    <div class="job-description">
      ${sections
        .map(
          (section) => `
            <section class="jd-block">
              <h4>${escapeHtml(section.title)}</h4>

              <ul class="jd-list">
                ${section.items
                  .map(
                    (item) => `
                      <li>${escapeHtml(item)}</li>
                    `,
                  )
                  .join("")}
              </ul>
            </section>
          `,
        )
        .join("")}
    </div>
  `;
}


function renderJobDescriptionComposerSummary(job) {
  if (
    !state.matchingMode ||
    !job ||
    !elements.jobDescriptionSummary
  ) {
    elements.jobDescriptionSummary.hidden = true;
    elements.jobDescriptionSummary.innerHTML = "";
    elements.jobDescriptionInput.hidden = false;

    if (elements.editJdButton) {
      elements.editJdButton.hidden = true;
    }

    return;
  }

  const skills = Array.isArray(job.skills)
    ? job.skills.slice(0, 4)
    : [];
  const salary = formatSalary(job);

  elements.jobDescriptionSummary.hidden = false;
  elements.jobDescriptionInput.hidden = true;

  if (elements.editJdButton) {
    elements.editJdButton.hidden = false;
  }

  elements.jobDescriptionSummary.innerHTML = `
    <div>
      <span class="jd-summary-kicker">JD đã tự điền</span>
      <strong>${escapeHtml(job.title || "Công việc đang chọn")}</strong>
      <small>${escapeHtml(job.company || "Chưa có công ty")}</small>
    </div>

    <dl>
      ${renderSummaryMetric("Địa điểm", job.location)}
      ${renderSummaryMetric("Hình thức", getWorkModeLabel(job.work_mode))}
      ${renderSummaryMetric("Cấp độ", getSeniorityLabel(job.seniority_level))}
      ${salary ? renderSummaryMetric("Lương", salary) : ""}
    </dl>

    ${
      skills.length
        ? `<div class="jd-summary-skills">
            ${skills
              .map((skill) => `<span>${escapeHtml(skill)}</span>`)
              .join("")}
          </div>`
        : ""
    }
  `;
}


function renderSummaryMetric(label, value) {
  if (!value) {
    return "";
  }

  return `
    <div>
      <dt>${escapeHtml(label)}</dt>
      <dd>${escapeHtml(value)}</dd>
    </div>
  `;
}


function showJobDescriptionEditor() {
  elements.jobDescriptionSummary.hidden = true;
  elements.jobDescriptionInput.hidden = false;
  elements.editJdButton.hidden = true;
  elements.jobDescriptionInput.focus();
}


function parseJobDescriptionSections(description) {
  const lines = String(description ?? "")
    .split(/\r?\n/)
    .map((line) => normalizeDescriptionLine(line))
    .filter(Boolean);

  if (!lines.length) {
    return [];
  }

  const sections = [];
  let currentSection = createDescriptionSection("Thông tin công việc");

  for (const line of lines) {
    const heading = normalizeDescriptionHeading(line);

    if (heading) {
      if (currentSection.items.length) {
        sections.push(currentSection);
      }

      currentSection = createDescriptionSection(heading);
      continue;
    }

    currentSection.items.push(line);
  }

  if (currentSection.items.length) {
    sections.push(currentSection);
  }

  return sections;
}


function createDescriptionSection(title) {
  return {
    title,
    items: [],
  };
}


function normalizeDescriptionLine(line) {
  return String(line ?? "")
    .replace(/^[\s•*+-]+/, "")
    .replace(/^\d+[.)]\s+/, "")
    .trim();
}


function normalizeDescriptionHeading(line) {
  const text = line.replace(/:$/, "").trim();
  const key = text.toLowerCase();

  const headings = {
    "about us": "Giới thiệu công ty",
    "about the company": "Giới thiệu công ty",
    "about the role": "Tổng quan vai trò",
    "the role": "Tổng quan vai trò",
    "job description": "Mô tả công việc",
    "what you will do": "Công việc sẽ làm",
    "your responsibilities": "Trách nhiệm chính",
    responsibilities: "Trách nhiệm chính",
    requirements: "Yêu cầu công việc",
    qualifications: "Yêu cầu công việc",
    "your profile": "Yêu cầu ứng viên",
    "what you bring": "Yêu cầu ứng viên",
    "must have": "Yêu cầu bắt buộc",
    "nice to have": "Điểm cộng",
    "preferred qualifications": "Điểm cộng",
    "tech stack": "Công nghệ sử dụng",
    skills: "Kỹ năng yêu cầu",
    benefits: "Quyền lợi",
    "what we offer": "Quyền lợi",
    "we offer": "Quyền lợi",
    perks: "Quyền lợi",
    "why us?": "Vì sao nên ứng tuyển?",
    "why us": "Vì sao nên ứng tuyển?",
    "why join us?": "Vì sao nên ứng tuyển?",
    "why join us": "Vì sao nên ứng tuyển?",
    "mô tả công việc": "Mô tả công việc",
    "trách nhiệm": "Trách nhiệm chính",
    "yêu cầu": "Yêu cầu công việc",
    "yêu cầu công việc": "Yêu cầu công việc",
    "yêu cầu ứng viên": "Yêu cầu ứng viên",
    "quyền lợi": "Quyền lợi",
    "phúc lợi": "Quyền lợi",
  };

  if (headings[key]) {
    return headings[key];
  }

  if (
    line.endsWith(":") &&
    text.length <= 80 &&
    text.split(/\s+/).length <= 10
  ) {
    return text;
  }

  return null;
}


function closeJobDetail() {
  const wasOpen = isJobDetailOpen();

  elements.jobDetailOverlay.hidden = true;

  elements.jobDetailDrawer.classList.remove("is-open");
  elements.jobDetailDrawer.setAttribute(
    "aria-hidden",
    "true",
  );

  state.selectedJob = null;

  if (
    wasOpen &&
    state.lastFocusedBeforeDrawer instanceof HTMLElement
  ) {
    state.lastFocusedBeforeDrawer.focus();
  }

  state.lastFocusedBeforeDrawer = null;
}


function isJobDetailOpen() {
  return elements.jobDetailDrawer.classList.contains("is-open");
}


function trapJobDetailFocus(event) {
  const focusableElements = elements.jobDetailDrawer.querySelectorAll(
    [
      "a[href]",
      "button:not([disabled])",
      "textarea:not([disabled])",
      "input:not([disabled])",
      "select:not([disabled])",
      "[tabindex]:not([tabindex='-1'])",
    ].join(","),
  );

  if (!focusableElements.length) {
    event.preventDefault();
    elements.jobDetailDrawer.focus();
    return;
  }

  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];

  if (
    event.shiftKey &&
    document.activeElement === firstElement
  ) {
    event.preventDefault();
    lastElement.focus();
    return;
  }

  if (
    !event.shiftKey &&
    document.activeElement === lastElement
  ) {
    event.preventDefault();
    firstElement.focus();
  }
}


function showJobLoading() {
  openResultsPanel();
  elements.resultsSummary.hidden = true;
  elements.jobSort.disabled = true;

  elements.jobResults.innerHTML = `
    <section
      class="job-loading"
      aria-label="Đang tìm công việc"
    >
      <div class="loading-status">
        <span class="loading-spinner"></span>

        <div>
          <strong>Đang tìm công việc phù hợp</strong>
          <small>
            Phân tích yêu cầu và xếp hạng kết quả...
          </small>
        </div>
      </div>

      ${createSkeletonCards(3)}
    </section>
  `;
}


function createSkeletonCards(count) {
  return Array.from(
    { length: count },
    () => `
      <article class="job-card skeleton-card">
        <div class="skeleton skeleton-title"></div>
        <div class="skeleton skeleton-company"></div>
        <div class="skeleton skeleton-row"></div>
        <div class="skeleton skeleton-row short"></div>
      </article>
    `,
  ).join("");
}


function showInitialJobState() {
  elements.resultsEyebrow.textContent = "JOB DISCOVERY";
  elements.resultsTitle.textContent = "Công việc phù hợp";
  elements.resultsSummary.hidden = true;
  elements.jobSort.disabled = true;
  elements.backToJobsButton.hidden = true;
  elements.activeFilters.innerHTML = "";
  updateMobileResultsBadge(0);

  elements.jobResults.innerHTML = `
    <section class="empty-state">
      <div class="empty-illustration">⌕</div>

      <h3>Bắt đầu tìm công việc</h3>

      <p>
        Hãy mô tả vị trí, địa điểm, kỹ năng hoặc
        cấp độ kinh nghiệm bạn mong muốn.
      </p>

      <div class="example-query">
        “Tìm công việc AI tại Hồ Chí Minh phù hợp
        với sinh viên mới ra trường.”
      </div>
    </section>
  `;
}


function showNoJobResults() {
  elements.jobResults.innerHTML = `
    <section class="empty-state">
      <div class="empty-illustration">0</div>

      <h3>Chưa tìm thấy công việc phù hợp</h3>

      <p>
        Bạn có thể thử mở rộng địa điểm, kỹ năng,
        cấp độ kinh nghiệm hoặc hình thức làm việc.
      </p>
    </section>
  `;
}


function showJobErrorState() {
  elements.resultsSummary.hidden = true;
  elements.jobSort.disabled = true;

  elements.jobResults.innerHTML = `
    <section class="empty-state">
      <div class="empty-illustration">!</div>

      <h3>Không thể tải kết quả</h3>

      <p>
        Hãy kiểm tra FastAPI, PostgreSQL và Qdrant,
        sau đó thử tìm kiếm lại.
      </p>
    </section>
  `;
}


function resetConversation() {
  const nextThreadId = createThreadId();

  saveThreadId(nextThreadId);
  state.messages = [];
  state.jobs = [];
  state.currentSearchResult = null;
  state.lastSearchQuery = "";
  state.currentSort = "relevance";
  state.selectedJob = null;
  state.currentWorkflow = null;
  state.workflowJobMatches = [];
  state.currentMatchingResult = null;
  state.currentCvAnalysisResult = null;
  state.currentCareerAdviceResult = null;
  state.currentCoverLetterResult = null;
  state.matchingMode = false;
  state.jobDescription = "";
  state.isSending = false;

  elements.messageList.innerHTML = "";
  elements.suggestionList.hidden = false;
  elements.messageInput.value = "";
  resizeMessageInput();
  elements.jobDescriptionInput.value = "";
  elements.jobSort.value = "relevance";

  setMatchingMode(false);

  clearError();
  closeJobDetail();
  showInitialJobState();
  closeResultsPanel();
  setResultsAvailability(false);
  updateSendButton();

  addMessage({
    role: "assistant",
    text:
      "Cuộc trò chuyện mới đã bắt đầu. " +
      "Bạn muốn tìm công việc hay cần hỗ trợ về CV?",
  });
}


function addMessage({ role, text }) {
  const message = {
    id: crypto.randomUUID(),
    role,
    text,
  };

  state.messages.push(message);

  const article = document.createElement("article");

  article.className =
    `message ${role}-message`;

  if (role === "assistant") {
    const avatar = document.createElement("div");

    avatar.className = "assistant-avatar";
    avatar.textContent = "AI";

    article.append(avatar);
  }

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  const paragraph = document.createElement("p");
  paragraph.textContent = text;

  bubble.append(paragraph);
  article.append(bubble);

  elements.messageList.append(article);

  scrollMessagesToBottom();
}


function showTypingIndicator() {
  if (document.querySelector("#typing-indicator")) {
    return;
  }

  const article = document.createElement("article");

  article.id = "typing-indicator";
  article.className =
    "message assistant-message";

  article.innerHTML = `
    <div class="assistant-avatar">AI</div>

    <div
      class="typing-indicator"
      aria-label="Job Search AI đang xử lý"
    >
      <span></span>
      <span></span>
      <span></span>
    </div>
  `;

  elements.messageList.append(article);

  scrollMessagesToBottom();
}


function removeTypingIndicator() {
  document
    .querySelector("#typing-indicator")
    ?.remove();
}


function setComposerDisabled(disabled) {
  elements.messageInput.disabled = disabled;
  elements.attachCvButton.disabled = disabled;
  elements.toggleJdButton.disabled = disabled;
  elements.jobDescriptionInput.disabled = disabled;
  elements.clearJdButton.disabled = disabled;

  elements.sendButton.disabled =
    disabled ||
    !hasComposerContent();
}


function updateComposerContext() {
  if (!elements.messageInput) {
    return;
  }

  const hasCv = Boolean(state.uploadedCvId);

  elements.chatForm?.setAttribute(
    "data-mode",
    state.matchingMode ? "matching" : "search",
  );

  elements.chatForm?.setAttribute(
    "data-cv-ready",
    String(hasCv),
  );

  elements.messageInput.placeholder = state.matchingMode
    ? "Nhập yêu cầu so khớp, ví dụ: đánh giá CV này với JD..."
    : hasCv
      ? "Tìm việc phù hợp với CV, kỹ năng hoặc mục tiêu tiếp theo..."
      : "Nhập vị trí, kỹ năng, địa điểm hoặc câu hỏi nghề nghiệp...";
}


function resizeMessageInput() {
  const textarea = elements.messageInput;

  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
}


function updateSendButton() {
  elements.sendButton.disabled =
    state.isSending ||
    !hasComposerContent();
}


function hasComposerContent() {
  return Boolean(
    elements.messageInput.value.trim() ||
    (
      state.matchingMode &&
      elements.jobDescriptionInput.value.trim()
    ),
  );
}


function showError(message) {
  elements.globalError.textContent = message;
  elements.globalError.hidden = false;
}


function clearError() {
  elements.globalError.textContent = "";
  elements.globalError.hidden = true;
}


function scrollMessagesToBottom() {
  elements.messageList.scrollTo({
    top: elements.messageList.scrollHeight,
    behavior: "smooth",
  });
}


function validateCvFile(file) {
  const isPdf =
    file.type === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf");

  if (!isPdf) {
    return "CV phải là tệp PDF.";
  }

  if (file.size > MAX_FILE_SIZE) {
    return "Dung lượng CV không được vượt quá 10 MB.";
  }

  return null;
}


function formatScore(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "0%";
  }

  const normalized = Math.max(
    0,
    Math.min(1, number),
  );

  return `${Math.round(normalized * 100)}%`;
}


function clampMatchingScore(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return 0;
  }

  return Math.max(0, Math.min(100, number));
}


function formatSalary(job) {
  const minimum = toFiniteNumber(job.salary_min);
  const maximum = toFiniteNumber(job.salary_max);

  if (minimum === null && maximum === null) {
    return "";
  }

  const currency = job.salary_currency ?? "";
  const period = getSalaryPeriodLabel(
    job.salary_period,
  );

  if (minimum !== null && maximum !== null) {
    return (
      `${formatMoney(minimum)} – ` +
      `${formatMoney(maximum)} ${currency}${period}`
    );
  }

  if (minimum !== null) {
    return (
      `Từ ${formatMoney(minimum)} ` +
      `${currency}${period}`
    );
  }

  return (
    `Đến ${formatMoney(maximum)} ` +
    `${currency}${period}`
  );
}


function formatMoney(value) {
  return new Intl.NumberFormat("vi-VN", {
    maximumFractionDigits: 0,
  }).format(value);
}


function formatDate(value) {
  if (!value) {
    return "Không xác định";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Không xác định";
  }

  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}


function toFiniteNumber(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return null;
  }

  const number = Number(value);

  return Number.isFinite(number)
    ? number
    : null;
}


function getStrategyLabel(strategy) {
  const labels = {
    hybrid: "Tìm kiếm kết hợp PostgreSQL và Qdrant",
    semantic: "Tìm kiếm ngữ nghĩa bằng Qdrant",
    postgres: "Tìm kiếm bằng PostgreSQL",
  };

  return labels[strategy] ?? "Tìm kiếm công việc";
}

function getCvQualityLabel(value) {
  const labels = {
    excellent: "Rất tốt",
    good: "Tốt",
    needs_improvement: "Cần cải thiện",
    weak: "Còn yếu",
  };

  return labels[value] ?? "Chưa xác định";
}


function getCvQualityBadgeClass(value) {
  const classes = {
    excellent: "strong_match",
    good: "good_match",
    needs_improvement: "partial_match",
    weak: "low_match",
  };

  return classes[value] ?? "partial_match";
}


function getImprovementPriorityLabel(value) {
  const labels = {
    high: "Ưu tiên cao",
    medium: "Ưu tiên vừa",
    low: "Ưu tiên thấp",
  };

  return labels[value] ?? "Ưu tiên vừa";
}


function getCvSectionLabel(value) {
  const labels = {
    personal_information: "Thông tin cá nhân",
    professional_summary: "Giới thiệu",
    skills: "Kỹ năng",
    work_experience: "Kinh nghiệm",
    education: "Học vấn",
    projects: "Dự án",
    certifications: "Chứng chỉ",
    languages: "Ngoại ngữ",
    general: "Tổng thể",
  };

  return labels[value] ?? "Tổng thể";
}

function getRecommendationLabel(value) {
  const labels = {
    strong_match: "Rất phù hợp",
    good_match: "Phù hợp",
    partial_match: "Phù hợp một phần",
    low_match: "Mức độ phù hợp thấp",
  };

  return labels[value] ?? "Chưa xác định";
}


function getEvidenceStatusLabel(value) {
  const labels = {
    matched: "Đáp ứng",
    partial: "Một phần",
    missing: "Còn thiếu",
    not_applicable: "Không áp dụng",
  };

  return labels[value] ?? "Chưa xác định";
}


function getSeniorityLabel(value) {
  const labels = {
    intern: "Thực tập",
    fresher: "Fresher",
    junior: "Junior",
    middle: "Middle",
    senior: "Senior",
    lead: "Lead",
    manager: "Quản lý",
    director: "Giám đốc",
    unknown: "Không xác định",
  };

  return labels[value] ?? "Không xác định";
}


function getWorkModeLabel(value) {
  const labels = {
    onsite: "Tại văn phòng",
    remote: "Từ xa",
    hybrid: "Kết hợp",
    unknown: "Không xác định",
  };

  return labels[value] ?? "Không xác định";
}


function getEmploymentTypeLabel(value) {
  const labels = {
    full_time: "Toàn thời gian",
    part_time: "Bán thời gian",
    contract: "Hợp đồng",
    internship: "Thực tập",
    freelance: "Freelance",
    temporary: "Tạm thời",
    other: "Khác",
  };

  return labels[value] ?? "Không xác định";
}


function getSalaryPeriodLabel(value) {
  const labels = {
    hourly: "/giờ",
    weekly: "/tuần",
    fortnightly: "/2 tuần",
    monthly: "/tháng",
    annual: "/năm",
  };

  return labels[value] ?? "";
}


function safeExternalUrl(value) {
  if (!value) {
    return null;
  }

  try {
    const url = new URL(value);

    if (
      url.protocol !== "http:" &&
      url.protocol !== "https:"
    ) {
      return null;
    }

    return url.toString();
  } catch {
    return null;
  }
}


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
