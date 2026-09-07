const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const ENDPOINTS = {
  conversation: "/api/v1/conversation/messages",
  joSearch: "/api/v1/jobs/search",
  cvUpload: "/api/v1/cvs",
}

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export async function sendConversationMessage({
  threadId,
  message,
  cvId = null,
  jobDescription = null,
}) {
  const responseBody = await requestJson(
    ENDPOINTS.conversation,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        thread_id: threadId,
        message,
        cv_id: cvId,
        job_description: jobDescription,
      }),
    },
    "Không thể kết nối với dịch vụ hội thoại.",
  );

  return normalizeConversationResponse(responseBody)

}

export async function getConversationHistory(threadId) {
  const encodedThreadId = encodeURIComponent(threadId);

  const responseBody = await requestJson(
    `/api/v1/conversation/threads/${encodedThreadId}/messages`,
    {
      method: "GET",
    },
    "Không thể tải lịch sử cuộc trò chuyện.",
  );

  const data = responseBody?.data ?? responseBody;

  return {
    threadId: data?.thread_id ?? threadId,
    messages: Array.isArray(data?.messages)
      ? data.messages
          .filter(
            (message) =>
              message?.role === "user" ||
              message?.role === "assistant",
          )
          .map((message) => ({
            id: message?.message_id ?? crypto.randomUUID(),
            role: message.role,
            text: message?.content ?? "",
          }))
          .filter((message) => message.text.trim())
      : [],
  };
}

export async function searchJobs({
  query,
  filters = {},
  sort = "relevance",
  page = 1,
  pageSize = 10,
}) {
  const responseBody = await requestJson(
    ENDPOINTS.joSearch,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query,
        filters,
        sort,
        page,
        page_size: pageSize,
      }),
    },
    "Không thể kết nối với dịch vụ tìm kiếm việc làm.",
  );

  const data = responseBody?.data ?? responseBody;

  return normalizeJobSearchResult(data);
}

export async function uploadCv(file) {
  const formData = new FormData();
  formData.append("file", file);

  const responseBody = await requestJson(
    ENDPOINTS.cvUpload,
    {
      method: "POST",
      body: formData,
    },
    "Không thể tải CV lên backend.",
  );

  const data = responseBody?.data ?? responseBody;

  return {
    fileId: data?.fileId ?? data?.file_id ?? null,
    fileName: data?.fileName ?? data?.file_name ?? file.name,
    fileSize: data?.fileSize ?? data?.file_size ?? file.size,
    contentType: data?.content_type ?? file.type,
    inspection: data?.inspection ?? null,
    extraction: data?.extraction ?? null,
    ocr: data?.ocr ?? null,
    profile: data?.profile ?? null,
  };
}

export async function requestJson(endpoint, options, networkErrorMessage) {
  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}${endpoint}`,
      options,
    );
  } catch (error) {
    throw new ApiError(
      `${networkErrorMessage} Hãy kiểm tra FastAPI và CORS.`,
      0,
      error,
    );
  }

  const responseBody = await parseJsonResponse(response);

  if (!response.ok) {
    throw new ApiError(
      extractErrorMessage(responseBody),
      response.status,
      responseBody,
    );
  }

  return responseBody;
}

async function parseJsonResponse(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function normalizeConversationResponse(responseBody) {
  const data = responseBody?.data ?? responseBody;
  const intent = data?.intent ?? {};

  return {
    threadId: data?.thread_id ?? null,
    answer: data?.assistant_message ?? "Hệ thống đã tiếp nhận yêu cầu của bạn.",
    status: data?.status ?? "completed",
    route: data?.route ?? "general_question",
    primaryIntent: intent?.primary_intent ?? "general_question",
    confidence: typeof intent?.confidence === "number" ? intent.confidence : null,
    cvId: data?.cv_id ?? null,
    missingInputs: Array.isArray(data?.missing_inputs) ? data.missing_inputs : [],
    workflow: normalizeWorkflow(data?.workflow),
    workflowJobMatches: Array.isArray(data?.workflow_job_matches) ? data.workflow_job_matches.map(normalizeWorkflowJobMatch) : [],
    cvAnalysisResult: data?.cv_analysis_result ? normalizeCvAnalysisResult(data.cv_analysis_result) : null,
    careerAdviceResult: data?.career_advice_result ? normalizeCareerAdviceResult(data.career_advice_result) : null,
    coverLetterResult: data?.cover_letter_result ? normalizeCoverLetterResult(data.cover_letter_result) : null,
    jobSearchResult: data?.job_search_result ? normalizeJobSearchResult(data.job_search_result) : null,
    jobMatchingResult: data?.job_matching_result
      ? normalizeJobMatchingResult(data.job_matching_result)
      : null,
  };
}

function normalizeWorkflow(data) {
  if (!data || typeof data !== "object") {
    return null;
  }

  return {
    workflowType:
      data.workflow_type ?? "single_agent",

    steps: Array.isArray(data.steps) ? data.steps : [],

    currentStep:
      data.current_step ?? null,

    completedSteps: Array.isArray(data.completed_steps) ? data.completed_steps : [],
  };
}

function normalizeWorkflowJobMatch(data) {
  return {
    job: data?.job ?? {},

    match: data?.match ? normalizeJobMatchingResult(data.match) : null,
  };
}

function normalizeCoverLetterResult(data) {
  return {
    language: data?.language ?? "vi",
    tone: data?.tone ?? "professional",
    subject: data?.subject ?? "",
    salutation: data?.salutation ?? "",
    openingParagraph:data?.opening_paragraph ?? "",
    bodyParagraphs: normalizeStringList(data?.body_paragraphs),
    closingParagraph: data?.closing_paragraph ?? "",
    complimentaryClose: data?.complimentary_close ?? "",
    signatureName: data?.signature_name ?? null,
    cvEvidenceUsed: normalizeStringList(data?.cv_evidence_used),
    jobRequirementsAddressed: normalizeStringList(data?.job_requirements_addressed),
    confidence: toNullableNumber(data?.confidence),
    fullText: data?.full_text ?? "",
    wordCount: toNumber(data?.word_count),
    isPersonalized: Boolean(data?.is_personalized),
  };
}

function normalizeCareerAdviceResult(data) {
  return {
    careerGoal: data?.career_goal ?? "",
    isPersonalized: Boolean(data?.is_personalized),
    topPrioritySkills: normalizeStringList(data?.top_priority_skills),

    recommendedRoles: Array.isArray(data?.recommended_roles)
      ? data.recommended_roles.map(normalizeCareerRole)
      : [],

    skillGaps: Array.isArray(data?.skill_gaps)
      ? data.skill_gaps.map(normalizeCareerSkillGap)
      : [],

    roadmap: Array.isArray(data?.roadmap)
      ? data.roadmap.map(normalizeCareerRoadmapStep)
      : [],

    portfolioProjects: Array.isArray(data?.portfolio_projects)
      ? data.portfolio_projects.map(normalizePortfolioProject)
      : [],

    nextActions: Array.isArray(data?.next_actions)
      ? data.next_actions.map(normalizeCareerNextAction)
      : [],

    summary: data?.summary ?? "",
    confidence: toNullableNumber(data?.confidence),
  };
}

function normalizeCareerRole(data) {
  return {
    roleTitle: data?.role_title ?? "",
    readinessLevel: data?.readiness_level ?? "exploring",
    rationale: data?.rationale ?? "",
    cvEvidence: normalizeStringList(data?.cv_evidence),
    developmentNeeds: normalizeStringList(data?.development_needs),
  };
}

function normalizeCareerSkillGap(data) {
  return {
    skill: data?.skill ?? "",
    priority: data?.priority ?? "medium",
    reason: data?.reason ?? "",
    currentEvidence: normalizeStringList(data?.current_evidence),
    recommendedAction: data?.recommended_action ?? "",
  };
}

function normalizeCareerRoadmapStep(data) {
  return {
    phase: toNumber(data?.phase),
    title: data?.title ?? "",
    timeframe: data?.timeframe ?? "",
    objective: data?.objective ?? "",
    actions: normalizeStringList(data?.actions),
    successCriteria: normalizeStringList(data?.success_criteria),
  };
}

function normalizePortfolioProject(data) {
  return {
    title: data?.title ?? "",
    purpose: data?.purpose ?? "",
    skillsPracticed: normalizeStringList(data?.skills_practiced),
    suggestedFeatures: normalizeStringList(data?.suggested_features),
    expectedDeliverable: data?.expected_deliverable ?? "",
  };
}

function normalizeCareerNextAction(data) {
  return {
    priority: data?.priority ?? "medium",
    action: data?.action ?? "",
    reason: data?.reason ?? "",
    timeframe: data?.timeframe ?? null,
  };
}

function normalizeCvAnalysisResult(data) {
  const breakdown = data?.breakdown ?? {};

  return {
    overallScore: toNumber(data?.overall_score),
    qualityLevel: data?.quality_level ?? "needs_improvement",

    breakdown: {
      completeness: toNumber(breakdown?.completeness),
      professionalSummary: toNumber(breakdown?.professional_summary),
      skills: toNumber(breakdown?.skills),
      workExperience: toNumber(breakdown?.work_experience),
      projects: toNumber(breakdown?.projects),
      educationAndCredentials: toNumber(breakdown?.education_and_credentials),
    },

    strengths: Array.isArray(data?.strengths)
      ? data.strengths.map(normalizeCvFinding) : [],

    weaknesses: Array.isArray(data?.weaknesses)
      ? data.weaknesses.map(normalizeCvFinding) : [],

    improvements: Array.isArray(data?.improvements)
      ? data.improvements.map(normalizeCvImprovement) : [],

    summary: data?.summary ?? "",
    confidence: toNullableNumber(data?.confidence),
  };
}


function normalizeCvFinding(finding) {
  return {
    dimension: finding?.dimension ?? "completeness",
    section: finding?.section ?? "general",
    finding: finding?.finding ?? "",
    cvEvidence: normalizeStringList(finding?.cv_evidence),
  };
}


function normalizeCvImprovement(improvement) {
  return {
    section: improvement?.section ?? "general",
    priority: improvement?.priority ?? "medium",
    issue: improvement?.issue ?? "",
    suggestion: improvement?.suggestion ?? "",
    example:
      typeof improvement?.example === "string"
        ? improvement.example
        : null,
  };
}

function normalizeJobMatchingResult(data) {
  const breakdown = data?.breakdown ?? {};

  return {
    jobId: data?.job_id ?? null,
    overallScore: toNumber(data?.overall_score),
    recommendation: data?.recommendation ?? "low_match",
    breakdown: {
      technicalSkills: toNumber(breakdown?.technical_skills),
      experience: toNumber(breakdown?.experience),
      education: toNumber(breakdown?.education),
      projects: toNumber(breakdown?.projects),
      languagesAndCertifications: toNumber(
        breakdown?.language_and_certifications,
      ),
    },
    strengths: normalizeStringList(data?.strengths),
    gaps: normalizeStringList(data?.gaps),
    evidence: Array.isArray(data?.evidence)
      ? data.evidence.map(normalizeMatchEvidence)
      : [],
    summary: data?.summary ?? "",
    confidence: toNullableNumber(data?.confidence),
  };
}

function normalizeMatchEvidence(evidence) {
  return {
    dimension: evidence?.dimension ?? "technical_skills",
    requirement: evidence?.requirement ?? "",
    cvEvidence: normalizeStringList(evidence?.cv_evidence),
    status: evidence?.status ?? "missing",
    explanation: evidence?.explanation ?? "",
  };
}

function normalizeStringList(value) {
  return Array.isArray(value)
    ? value.filter((item) => typeof item === "string" && item.trim())
    : [];
}

function normalizeJobSearchResult(data) {
  if (!data || typeof data !== "object") {
    return {
      query: "",
      strategy: "postgres",
      total: 0,
      page: 1,
      pageSize: 10,
      items: [],
    };
  }

  const items = Array.isArray(data.items)
    ? data.items.map(normalizeJobSearchHit) : [];

  return {
    query: data.query ?? "",
    strategy: data.strategy ?? "postgres",
    total: typeof data.total === "number" ? data.total : items.length,
    page: typeof data.page === "number" ? data.page: 1,
    pageSize: typeof data.page_size === "number" ? data.page_size : 10,
    items,
  };
}

function normalizeJobSearchHit(hit) {
  return {
    job: hit?.job ?? {},
    score: {
      semantic: toNullableNumber(hit?.score?.semantic),
      keyword: toNumber(hit?.score?.keyword),
      filterMatch: toNumber(hit?.score?.filter_match),
      freshness: toNumber(hit?.score?.freshness),
      final: toNumber(hit?.score?.final),
    },
    matchedTerms: Array.isArray(hit?.matched_terms) ? hit.matched_terms : [],
    reasons: Array.isArray(hit?.reasons) ? hit.reasons : [],
  };
}

function toNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function toNullableNumber(value) {
  if (value === null || value === undefined) {
    return null
  }

  const number = Number(value)

  return Number.isFinite(number) ? number : null;
}
function extractErrorMessage(responseBody) {
  const validationDetails = responseBody?.detail

  if (Array.isArray(validationDetails)) {
    return validationDetails
    .map((item) => item?.msg)
    .filter(Boolean)
    .join("; ");
  }
  return (
    responseBody?.error?.message ||
    responseBody?.message ||
    responseBody?.detail ||
    "Không thể xử lý yêu cầu." 
  );
}
