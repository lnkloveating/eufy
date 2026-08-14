"""AI roles for forecasting, concept generation, review, and definition."""

from .forecasting import (
    CandidateNoveltyAuditorAgent,
    CandidateReviewerAgent,
    CompetitorAnalysisAgent,
    CurrentProductAuditorAgent,
    ForecastConsensusAgent,
    FuturesLensAgent,
    LensDeliberationAgent,
    OpportunitySynthesizerAgent,
    PortfolioDiversityAuditorAgent,
    ProductArchitectAgent,
    ProductDefinitionAgent,
    ProductSpecAnalystAgent,
    ProductSpecReviserAgent,
)

__all__ = [
    "CandidateReviewerAgent",
    "CandidateNoveltyAuditorAgent",
    "CompetitorAnalysisAgent",
    "CurrentProductAuditorAgent",
    "ForecastConsensusAgent",
    "FuturesLensAgent",
    "LensDeliberationAgent",
    "OpportunitySynthesizerAgent",
    "PortfolioDiversityAuditorAgent",
    "ProductArchitectAgent",
    "ProductDefinitionAgent",
    "ProductSpecAnalystAgent",
    "ProductSpecReviserAgent",
]
