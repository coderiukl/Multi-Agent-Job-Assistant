from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.agents import (
    CareerAdviceAgent,
    CoverLetterAgent,
    CVAnalysisAgent,
    CVParserAgent,
    JobMatchingAgent,
    JobSearchAgent,
)
from app.core.config import get_settings
from app.database import (
    JobSessionFactory,
    create_job_database_engine,
    create_job_session_factory,
)
from app.embeddings import EmbeddingFactory
from app.graphs.conversation import ConversationNodes, build_conversation_graph
from app.llm import LLMFactory
from app.memory import ConversationMemory
from app.repositories.cv import CVRepository, LocalJsonCVRepository
from app.repositories.postgres_job_search import PostgresJobSearchRepository
from app.services.career_advice import CareerAdviceService
from app.services.conversation import ConversationIntentAnalyzer, ConversationService
from app.services.cover_letter import CoverLetterService
from app.services.cv_analysis import CVAnalysisService
from app.services.cv_ingestion import CVIngestionService
from app.services.cv_processing import CVProcessingService
from app.services.job_matching import JobMatchingService
from app.services.job_search import HybridJobSearchService
from app.services.pdf import (
    NativePdfTextExtractor,
    PdfInspector,
    PdfOcrExtractor,
    PdfTextMerger,
)
from app.services.storage import LocalStorageService, StorageService
from app.vectorstores import QdrantJobVectorIndex, create_qdrant_client


@lru_cache
def get_storage_service() -> StorageService:
    return LocalStorageService(get_settings())


@lru_cache
def get_cv_repository() -> CVRepository:
    return LocalJsonCVRepository(get_settings())


@lru_cache
def get_pdf_inspector() -> PdfInspector:
    return PdfInspector(get_settings())


@lru_cache
def get_native_pdf_text_extractor() -> NativePdfTextExtractor:
    return NativePdfTextExtractor(get_settings())


@lru_cache
def get_pdf_ocr_extractor() -> PdfOcrExtractor:
    return PdfOcrExtractor(get_settings())


@lru_cache
def get_pdf_text_merger() -> PdfTextMerger:
    return PdfTextMerger()


@lru_cache
def get_chat_model() -> BaseChatModel:
    return LLMFactory.create_chat_model(get_settings())


@lru_cache
def get_cv_analysis_agent() -> CVAnalysisAgent:
    return CVAnalysisAgent(llm=get_chat_model(), settings=get_settings())


@lru_cache
def get_cv_analysis_service() -> CVAnalysisService:
    return CVAnalysisService(agent=get_cv_analysis_agent())


CVAnalysisServiceDependency = Annotated[
    CVAnalysisService,
    Depends(get_cv_analysis_service),
]


@lru_cache
def get_career_advice_agent() -> CareerAdviceAgent:
    return CareerAdviceAgent(
        llm=get_chat_model(),
        settings=get_settings(),
    )


@lru_cache
def get_career_advice_service() -> CareerAdviceService:
    return CareerAdviceService(
        agent=get_career_advice_agent(),
    )


CareerAdviceServiceDependency = Annotated[
    CareerAdviceService,
    Depends(get_career_advice_service),
]


@lru_cache
def get_cover_letter_agent() -> CoverLetterAgent:
    return CoverLetterAgent(
        llm=get_chat_model(),
        settings=get_settings(),
    )


@lru_cache
def get_cover_letter_service() -> CoverLetterService:
    return CoverLetterService(
        agent=get_cover_letter_agent(),
    )


def get_cv_parser_agent(llm: BaseChatModel = Depends(get_chat_model)) -> CVParserAgent:
    return CVParserAgent(llm=llm, settings=get_settings())


def get_cv_ingestion_service(
    storage_service: StorageService = Depends(get_storage_service),
    pdf_inspector: PdfInspector = Depends(get_pdf_inspector),
    text_extractor: NativePdfTextExtractor = Depends(get_native_pdf_text_extractor),
    ocr_extractor: PdfOcrExtractor = Depends(get_pdf_ocr_extractor),
    text_merger: PdfTextMerger = Depends(get_pdf_text_merger),
) -> CVIngestionService:
    return CVIngestionService(
        storage=storage_service,
        pdf_inspector=pdf_inspector,
        text_extractor=text_extractor,
        ocr_extractor=ocr_extractor,
        text_merger=text_merger,
    )


def get_cv_processing_service(
    ingestion_service: CVIngestionService = Depends(get_cv_ingestion_service),
    parser_agent: CVParserAgent = Depends(get_cv_parser_agent),
    storage_service: StorageService = Depends(get_storage_service),
    cv_repository: CVRepository = Depends(get_cv_repository),
) -> CVProcessingService:
    return CVProcessingService(
        ingestion_service=ingestion_service,
        parser_agent=parser_agent,
        storage_service=storage_service,
        cv_repository=cv_repository,
    )


CVIngestionServiceDependency = Annotated[
    CVIngestionService,
    Depends(get_cv_ingestion_service),
]

CVProcessingServiceDependency = Annotated[
    CVProcessingService,
    Depends(get_cv_processing_service),
]

ChatModelDependency = Annotated[BaseChatModel, Depends(get_chat_model)]

# Job Search dependencies


@lru_cache
def get_job_database_engine() -> AsyncEngine:
    return create_job_database_engine(get_settings())


@lru_cache
def get_job_session_factory() -> JobSessionFactory:
    return create_job_session_factory(get_job_database_engine())


@lru_cache
def get_job_search_repository() -> PostgresJobSearchRepository:
    return PostgresJobSearchRepository(get_job_session_factory())


@lru_cache
def get_job_embeddings() -> Embeddings:
    return EmbeddingFactory.create(get_settings())


@lru_cache
def get_job_qdrant_client() -> AsyncQdrantClient:
    return create_qdrant_client(get_settings())


@lru_cache
def get_job_vector_index() -> QdrantJobVectorIndex:
    return QdrantJobVectorIndex(
        client=get_job_qdrant_client(),
        embeddings=get_job_embeddings(),
        settings=get_settings(),
    )


@lru_cache
def get_job_search_agent() -> JobSearchAgent:
    return JobSearchAgent(
        llm=get_chat_model(),
        settings=get_settings(),
    )


@lru_cache
def get_job_search_service() -> HybridJobSearchService:
    return HybridJobSearchService(
        agent=get_job_search_agent(),
        repository=get_job_search_repository(),
        vector_index=get_job_vector_index(),
        candidate_limit=100,
    )


JobSearchServiceDependency = Annotated[
    HybridJobSearchService,
    Depends(get_job_search_service),
]


async def close_job_search_resources() -> None:
    get_conversation_graph.cache_clear()

    if get_conversation_memory.cache_info().currsize:
        await get_conversation_memory().close()

    get_conversation_memory.cache_clear()

    if get_job_qdrant_client.cache_info().currsize:
        await get_job_qdrant_client().close()

    if get_job_database_engine.cache_info().currsize:
        await get_job_database_engine().dispose()

    get_cv_analysis_service.cache_clear()
    get_cv_analysis_agent.cache_clear()

    get_career_advice_service.cache_clear()
    get_career_advice_agent.cache_clear()

    get_cover_letter_service.cache_clear()
    get_cover_letter_agent.cache_clear()

    get_job_search_service.cache_clear()
    get_job_search_agent.cache_clear()

    get_job_matching_service.cache_clear()
    get_job_matching_agent.cache_clear()

    get_job_vector_index.cache_clear()
    get_job_qdrant_client.cache_clear()
    get_job_embeddings.cache_clear()
    get_job_search_repository.cache_clear()

    get_job_session_factory.cache_clear()
    get_job_database_engine.cache_clear()


@lru_cache
def get_job_matching_agent() -> JobMatchingAgent:
    return JobMatchingAgent(
        llm=get_chat_model(),
        settings=get_settings(),
    )


@lru_cache
def get_job_matching_service() -> JobMatchingService:
    return JobMatchingService(
        agent=get_job_matching_agent(),
    )


JobMatchingServiceDependency = Annotated[
    JobMatchingService,
    Depends(get_job_matching_service),
]


@lru_cache
def get_conversation_memory() -> ConversationMemory:
    return ConversationMemory(get_settings())


async def start_conversation_memory_resources() -> None:
    await get_conversation_memory().start()


@lru_cache
def get_conversation_graph() -> CompiledStateGraph:
    analyzer = ConversationIntentAnalyzer(llm=get_chat_model())
    nodes = ConversationNodes(
        analyzer=analyzer,
        cv_repository=get_cv_repository(),
        cv_analysis_service=get_cv_analysis_service(),
        career_advice_service=get_career_advice_service(),
        cover_letter_service=get_cover_letter_service(),
        job_search_service=get_job_search_service(),
        job_matching_service=get_job_matching_service(),
    )

    return build_conversation_graph(
        nodes, checkpointer=get_conversation_memory().checkpointer
    )


ConversationGraphDependency = Annotated[
    CompiledStateGraph, Depends(get_conversation_graph)
]


def get_conversation_service(graph: ConversationGraphDependency) -> ConversationService:
    return ConversationService(graph=graph)


ConversationServiceDependency = Annotated[
    ConversationService, Depends(get_conversation_service)
]
