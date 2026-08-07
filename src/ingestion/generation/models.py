"""Independent versioned schemas for local source-grounded generation."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import Field, model_validator

from ingestion.normalization.models import CanonicalModel, SourceReference

GENERATION_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"


class ProviderKind(str, Enum):
    MOCK = "mock"
    OLLAMA = "ollama"


class ContentType(str, Enum):
    QCM = "qcm"
    TRUE_FALSE = "true_false"
    FLASHCARD = "flashcard"
    SUMMARY = "summary"
    LEARNING_OBJECTIVE = "learning_objective"
    REVISION_QUIZ = "revision_quiz"
    CLINICAL_CASE = "clinical_case"


class QCMType(str, Enum):
    SINGLE_ANSWER = "single_answer"
    MULTIPLE_ANSWER = "multiple_answer"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class KnowledgeMode(str, Enum):
    SOURCE_ONLY = "source_only"


class GenerationStatus(str, Enum):
    DRAFT = "draft"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class ReportStatus(str, Enum):
    SUCCESS = "success"
    NEEDS_REVISION = "needs_revision"
    FAILED = "failed"


class FailureStage(str, Enum):
    PROVIDER_RESPONSE = "provider_response"
    STRUCTURED_PARSING = "structured_parsing"
    MATERIALIZATION = "materialization"
    CONTENT_VALIDATION = "content_validation"


class ReviewDecision(CanonicalModel):
    decision: ReviewStatus
    reviewer: str
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str | None = None

    @model_validator(mode="after")
    def reject_unreviewed_decision(self) -> ReviewDecision:
        if self.decision is ReviewStatus.UNREVIEWED:
            raise ValueError("A review decision cannot return content to unreviewed.")
        if not self.reviewer.strip():
            raise ValueError("Reviewer must be nonempty.")
        return self


class HumanReviewState(CanonicalModel):
    status: ReviewStatus = ReviewStatus.UNREVIEWED
    decisions: list[ReviewDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_history(self) -> HumanReviewState:
        if len(self.decisions) > 1:
            raise ValueError("Accepted, rejected, and needs_revision review states are terminal.")
        expected = self.decisions[-1].decision if self.decisions else ReviewStatus.UNREVIEWED
        if self.status is not expected:
            raise ValueError("Review status does not match decision history.")
        return self


class ProviderMetadata(CanonicalModel):
    provider: ProviderKind
    model: str
    base_url: str | None = None
    attempt_count: int = Field(default=1, ge=1)
    seed: int | None = None
    temperature: float = Field(ge=0)
    context_size: int = Field(gt=0)
    maximum_output_tokens: int = Field(gt=0)
    raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_version: str | None = None


class GenerationConfiguration(CanonicalModel):
    content_type: ContentType
    qcm_type: QCMType | None = None
    count: int = Field(ge=1, le=100)
    language: str = Field(min_length=2)
    difficulty_distribution: dict[Difficulty, int]
    knowledge_mode: KnowledgeMode = KnowledgeMode.SOURCE_ONLY
    provider: ProviderKind = ProviderKind.OLLAMA
    model: str = Field(min_length=1)
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = Field(default=120.0, gt=0)
    temperature: float = Field(default=0.0, ge=0, le=2)
    context_size: int = Field(default=8192, gt=0)
    seed: int | None = 42
    maximum_output_tokens: int = Field(default=2048, gt=0)
    retry_count: int = Field(default=2, ge=0, le=10)
    validation_retry_count: int = Field(default=1, ge=0, le=10)
    maximum_source_characters: int = Field(default=12000, gt=0)
    maximum_source_tokens: int = Field(default=3000, gt=0)
    topic: str | None = None

    @model_validator(mode="after")
    def validate_generation_configuration(self) -> GenerationConfiguration:
        if self.content_type is ContentType.QCM and self.qcm_type is None:
            raise ValueError("QCM generation requires an explicit qcm_type.")
        if self.content_type is not ContentType.QCM and self.qcm_type is not None:
            raise ValueError("qcm_type is valid only for QCM content.")
        if sum(self.difficulty_distribution.values()) != self.count:
            raise ValueError("Difficulty counts must sum to the requested content count.")
        if any(value < 0 for value in self.difficulty_distribution.values()):
            raise ValueError("Difficulty counts cannot be negative.")
        return self


class SourceChunkReference(CanonicalModel):
    chunk_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_index: int = Field(ge=0)
    chunk_type: str
    text: str = Field(min_length=1)
    normalized_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    character_count: int = Field(gt=0)
    token_estimate: int = Field(gt=0)
    source_references: list[SourceReference] = Field(min_length=1)


class GenerationSource(CanonicalModel):
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_relative_path: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_schema_version: str
    eligible_chunk_count: int = Field(ge=0)
    ineligible_chunk_count: int = Field(ge=0)
    selected_chunks: list[SourceChunkReference] = Field(min_length=1)
    excluded_chunk_ids: list[str]
    exclusion_reasons: dict[str, str]
    selected_character_count: int = Field(ge=0)
    selected_token_estimate: int = Field(ge=0)
    prompt_character_estimate: int = Field(ge=0)
    prompt_token_estimate: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_source_selection(self) -> GenerationSource:
        selected_ids = [chunk.chunk_id for chunk in self.selected_chunks]
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError("Selected generation chunks must be unique.")
        if set(selected_ids).intersection(self.excluded_chunk_ids):
            raise ValueError("A selected chunk cannot also be excluded.")
        if self.document_id != self.source_sha256:
            raise ValueError("Generation source document identity must match source SHA-256.")
        return self


class GenerationRequest(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    generation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    configuration: GenerationConfiguration
    source: GenerationSource
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceCitation(CanonicalModel):
    chunk_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    quotation: str = Field(min_length=1)


class QCMChoice(CanonicalModel):
    choice_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    text: str = Field(min_length=1)


class CorrectAnswer(CanonicalModel):
    choice_ids: list[str] = Field(min_length=1)


class Explanation(CanonicalModel):
    text: str = Field(min_length=1)
    evidence: list[EvidenceCitation] = Field(min_length=1)


class QCMQuestion(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    question_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    question_type: QCMType
    language: str = Field(min_length=2)
    topic: str = Field(min_length=1)
    difficulty: Difficulty
    stem: str = Field(min_length=1)
    choices: list[QCMChoice] = Field(min_length=3)
    correct_answer: CorrectAnswer
    explanation: Explanation
    source_document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_chunk_ids: list[str] = Field(min_length=1)
    source_references: list[SourceReference] = Field(min_length=1)
    provider_metadata: ProviderMetadata
    generation_status: Literal[GenerationStatus.DRAFT] = GenerationStatus.DRAFT
    medical_review: HumanReviewState = Field(default_factory=HumanReviewState)

    @model_validator(mode="after")
    def validate_qcm(self) -> QCMQuestion:
        choice_ids = [choice.choice_id for choice in self.choices]
        normalized_choices = [" ".join(choice.text.casefold().split()) for choice in self.choices]
        if len(choice_ids) != len(set(choice_ids)):
            raise ValueError("QCM choice IDs must be unique.")
        if len(normalized_choices) != len(set(normalized_choices)):
            raise ValueError("QCM choices must be textually unique.")
        correct = self.correct_answer.choice_ids
        if len(correct) != len(set(correct)) or not set(correct).issubset(choice_ids):
            raise ValueError("Correct-answer IDs must be unique existing choice IDs.")
        if self.question_type is QCMType.SINGLE_ANSWER and len(correct) != 1:
            raise ValueError("Single-answer QCM requires exactly one correct choice.")
        if self.question_type is QCMType.MULTIPLE_ANSWER and len(correct) < 2:
            raise ValueError("Multiple-answer QCM requires at least two correct choices.")
        if self.source_document_id != self.source_sha256:
            raise ValueError("QCM source document identity must match source SHA-256.")
        if len(self.source_chunk_ids) != len(set(self.source_chunk_ids)):
            raise ValueError("QCM source chunk IDs must be unique.")
        return self


class Flashcard(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    front: str
    back: str
    generation_status: Literal[GenerationStatus.DRAFT] = GenerationStatus.DRAFT
    medical_review: HumanReviewState = Field(default_factory=HumanReviewState)


class Summary(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    text: str
    generation_status: Literal[GenerationStatus.DRAFT] = GenerationStatus.DRAFT
    medical_review: HumanReviewState = Field(default_factory=HumanReviewState)


class ClinicalCase(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    presentation: str
    questions: list[str]
    generation_status: Literal[GenerationStatus.DRAFT] = GenerationStatus.DRAFT
    medical_review: HumanReviewState = Field(default_factory=HumanReviewState)


class LearningObjective(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    text: str


class TrueFalseQuestion(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    statement: str
    answer: bool


class RevisionQuiz(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    title: str
    question_ids: list[str]


class GeneratedContentBatch(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    generation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_type: ContentType
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    qcm_questions: list[QCMQuestion] = Field(default_factory=list)
    flashcards: list[Flashcard] = Field(default_factory=list)
    summaries: list[Summary] = Field(default_factory=list)
    clinical_cases: list[ClinicalCase] = Field(default_factory=list)
    learning_objectives: list[LearningObjective] = Field(default_factory=list)
    true_false_questions: list[TrueFalseQuestion] = Field(default_factory=list)
    revision_quizzes: list[RevisionQuiz] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_batch(self) -> GeneratedContentBatch:
        if self.document_id != self.source_sha256:
            raise ValueError("Generated batch document identity must match source SHA-256.")
        if self.content_type is ContentType.QCM and not self.qcm_questions:
            raise ValueError("A QCM batch must contain QCM questions.")
        if self.content_type is ContentType.QCM and any(
            (
                self.flashcards,
                self.summaries,
                self.clinical_cases,
                self.learning_objectives,
                self.true_false_questions,
                self.revision_quizzes,
            )
        ):
            raise ValueError("A QCM batch cannot contain reserved content types.")
        question_ids = [question.question_id for question in self.qcm_questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Generated question IDs must be unique.")
        return self


class ValidationIssue(CanonicalModel):
    severity: IssueSeverity
    code: str
    message: str
    question_id: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class GroundingReport(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    generation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ReportStatus
    grounded_question_count: int = Field(ge=0)
    needs_revision_question_ids: list[str]
    issues: list[ValidationIssue]
    note: str = (
        "Grounding checks are technical source-support checks and do not prove medical correctness."
    )


class GenerationValidationReport(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    generation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ReportStatus
    issue_count: int = Field(ge=0)
    issues: list[ValidationIssue]


class GenerationReport(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    generation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_time: datetime
    completion_time: datetime
    status: ReportStatus
    provider_metadata: ProviderMetadata
    requested_count: int = Field(ge=1)
    generated_count: int = Field(ge=0)
    selected_chunk_ids: list[str]
    warnings: list[str]
    errors: list[str]
    output_paths: list[str]
    parent_attempt_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    validation_retry_sequence: int = Field(default=0, ge=0)
    retry_issue_codes: list[str] = Field(default_factory=list)
    question_count_changed: bool | None = None


class RawProviderResponseRecord(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    exact_raw_http_response_text: str | None
    parsed_provider_envelope: dict[str, Any] | None
    provider_content: str | None
    http_status: int | None = Field(default=None, ge=100, le=599)


class FailureReport(CanonicalModel):
    generation_schema_version: Literal["1.0.0"] = GENERATION_SCHEMA_VERSION
    generation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at: datetime
    completed_at: datetime
    status: Literal[ReportStatus.FAILED] = ReportStatus.FAILED
    failure_stage: FailureStage
    failure_code: str
    failure_message: str
    exception_type: str
    exception_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_metadata: ProviderMetadata | None
    provider_attempt_count: int = Field(ge=1)
    http_status: int | None = Field(default=None, ge=100, le=599)
    raw_response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    raw_response_is_json: bool
    structural_issue_count: int = Field(ge=0)
    provenance_issue_count: int = Field(ge=0)
    grounding_issue_count: int = Field(ge=0)
    output_paths: list[str]
    parent_attempt_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    validation_retry_sequence: int = Field(default=0, ge=0)
    retry_issue_codes: list[str] = Field(default_factory=list)
    question_count_changed: bool | None = None

    @model_validator(mode="after")
    def validate_failure_identity(self) -> FailureReport:
        if self.document_id != self.source_sha256:
            raise ValueError("Failure report document identity must match source SHA-256.")
        if self.completed_at < self.started_at:
            raise ValueError("Failure completion time cannot precede its start time.")
        if self.validation_retry_sequence > 0 and self.parent_attempt_id is None:
            raise ValueError("A corrective retry must identify its parent failed attempt.")
        if self.validation_retry_sequence == 0 and self.parent_attempt_id is not None:
            raise ValueError("An initial attempt cannot identify a parent failed attempt.")
        return self


class ProviderQCMChoiceDraft(CanonicalModel):
    key: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ProviderEvidenceDraft(CanonicalModel):
    chunk_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_reference_block_ids: list[str] = Field(min_length=1)


class ProviderQCMQuestionDraft(CanonicalModel):
    topic: str = Field(min_length=1)
    difficulty: Difficulty
    stem: str = Field(min_length=1)
    choices: list[ProviderQCMChoiceDraft] = Field(min_length=3)
    correct_choice_keys: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    evidence: list[ProviderEvidenceDraft] = Field(min_length=1, max_length=1)


class ProviderQCMResponse(CanonicalModel):
    questions: list[ProviderQCMQuestionDraft] = Field(min_length=1)
    insufficient_evidence: bool = False
    shortfall_reason: str | None = None

    @model_validator(mode="after")
    def validate_shortfall_declaration(self) -> ProviderQCMResponse:
        if self.insufficient_evidence and not (self.shortfall_reason or "").strip():
            raise ValueError("insufficient_evidence=true requires a nonempty shortfall_reason.")
        if not self.insufficient_evidence and self.shortfall_reason is not None:
            raise ValueError("shortfall_reason is valid only when insufficient_evidence=true.")
        return self


class ProviderQCMReplacementDraft(CanonicalModel):
    question_ordinal: int = Field(ge=1)
    replacement: ProviderQCMQuestionDraft


class ProviderQCMCorrectionResponse(CanonicalModel):
    question_replacements: list[ProviderQCMReplacementDraft]
    insufficient_evidence: bool = False
    shortfall_reason: str | None = None

    @model_validator(mode="after")
    def validate_correction_declaration(self) -> ProviderQCMCorrectionResponse:
        ordinals = [item.question_ordinal for item in self.question_replacements]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("Corrective response question ordinals must be unique.")
        if self.insufficient_evidence and not (self.shortfall_reason or "").strip():
            raise ValueError("insufficient_evidence=true requires a nonempty shortfall_reason.")
        if not self.insufficient_evidence and self.shortfall_reason is not None:
            raise ValueError("shortfall_reason is valid only when insufficient_evidence=true.")
        return self
