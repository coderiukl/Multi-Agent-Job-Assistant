from langchain_core.language_models.chat_models import BaseChatModel

from app.prompts.intent_analysis import INTENT_ANALYSIS_PROMPT
from app.schemas.conversations_intent import IntentAnalysisInput, IntentAnalysisResult

class ConversationIntentAnalyzer:
    def __init__(self, llm: BaseChatModel) -> None:
        structured_llm = llm.with_structured_output(IntentAnalysisResult)
        self._chain = INTENT_ANALYSIS_PROMPT | structured_llm   

    async def analyze(self, input_data: IntentAnalysisInput) -> IntentAnalysisResult:
        result = await self._chain.ainvoke(
            {
                "message": input_data.message,
                "conversation_history": input_data.conversation_history,
                "has_cv": input_data.has_cv,
                "has_jd": input_data.has_jd,
            }
        )

        return IntentAnalysisResult.model_validate(result)