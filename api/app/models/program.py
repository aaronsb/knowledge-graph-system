"""
GraphProgram AST Models (ADR-500)

Pydantic models for the GraphProgram domain-specific query composition language.
These models define the canonical JSON AST that all authoring surfaces compile to.

The AST represents a finite sequence of set-algebraic operations over openCypher
queries and REST API calls. Programs are bounded by construction: no iteration,
no user-defined abstractions, no mutable variables, no recursion.

Zero platform dependencies: pure Python + Pydantic only. No database, no FastAPI,
no AGE client. Importable and testable from a bare ``pytest`` run without Docker.

Usage:
    from api.app.models.program import GraphProgram

    program = GraphProgram.model_validate(json_data)

@verified 0000000
"""

from typing import Optional, List, Union, Literal, Dict, Any
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_OPERATORS = ('+', '-', '&', '?', '!')
"""Allowed set-algebra operator characters.  @verified 0000000"""

VALID_CONDITION_TESTS = (
    'has_results', 'empty',
    'count_gte', 'count_lte',
    'has_ontology', 'has_relationship',
)
"""Allowed condition test identifiers for ConditionalOp.  @verified 0000000"""

CYPHER_WRITE_KEYWORDS = frozenset({
    'CREATE', 'SET', 'DELETE', 'MERGE', 'REMOVE', 'DROP', 'DETACH',
})
"""Cypher keywords that indicate a write operation (deny list).  @verified 0000000"""

API_ENDPOINT_ALLOWLIST: Dict[str, Dict[str, Any]] = {
    '/search/concepts': {
        'required': ['query'],
        'optional': ['min_similarity', 'limit', 'ontology', 'offset'],
        'types': {
            'query': str, 'min_similarity': (int, float),
            'limit': int, 'ontology': str, 'offset': int,
        },
    },
    '/search/sources': {
        'required': ['query'],
        'optional': ['min_similarity', 'limit', 'ontology', 'offset'],
        'types': {
            'query': str, 'min_similarity': (int, float),
            'limit': int, 'ontology': str, 'offset': int,
        },
    },
    '/vocabulary/status': {
        'required': [],
        'optional': ['status_filter', 'relationship_type'],
        'types': {'status_filter': str, 'relationship_type': str},
    },
    '/concepts/batch': {
        'required': ['concept_ids'],
        'optional': ['include_details'],
        'types': {'concept_ids': list, 'include_details': bool},
    },
    '/concepts/details': {
        'required': ['concept_id'],
        'optional': ['include_diversity', 'include_grounding'],
        'types': {
            'concept_id': str, 'include_diversity': bool,
            'include_grounding': bool,
        },
    },
    '/concepts/related': {
        'required': ['concept_id'],
        'optional': ['max_depth', 'relationship_types'],
        'types': {
            'concept_id': str, 'max_depth': int,
            'relationship_types': list,
        },
    },
}
"""
Permitted API endpoints for ApiOp statements.

Each entry maps an endpoint path to its required and optional parameter names.
The ``types`` dict maps parameter names to expected Python types (or tuples of
types for multiple acceptable types, e.g., ``(int, float)``). Endpoints not in
this dict are rejected by the validator (V020). Parameter type mismatches
produce V023 errors.

@verified 0000000
"""

MAX_VARIABLE_PATH_LENGTH = 6
"""Maximum hops for variable-length Cypher paths (V030).  @verified 0000000"""

MAX_STATEMENTS = 100
"""Maximum total operation count per program (V006).  @verified 0000000"""

MAX_NESTING_DEPTH = 3
"""Maximum conditional nesting depth (V007).  @verified 0000000"""

CURRENT_VERSION = 1
"""Only supported program version.  @verified 0000000"""


# ---------------------------------------------------------------------------
# Operator type
# ---------------------------------------------------------------------------

Operator = Literal['+', '-', '&', '?', '!']
"""Set-algebra operator for a statement.  @verified 0000000"""


# ---------------------------------------------------------------------------
# Conditions (for ConditionalOp)
# ---------------------------------------------------------------------------

class HasResultsCondition(BaseModel):
    """Test whether the working graph W is non-empty.  @verified 0000000"""
    test: Literal['has_results']


class EmptyCondition(BaseModel):
    """Test whether the working graph W is empty.  @verified 0000000"""
    test: Literal['empty']


class CountGteCondition(BaseModel):
    """Test whether W has >= N nodes.  @verified 0000000"""
    test: Literal['count_gte']
    value: int = Field(..., gt=0)


class CountLteCondition(BaseModel):
    """Test whether W has <= N nodes.  @verified 0000000"""
    test: Literal['count_lte']
    value: int = Field(..., ge=0)


class HasOntologyCondition(BaseModel):
    """Test whether W contains nodes from a specific ontology.  @verified 0000000"""
    test: Literal['has_ontology']
    ontology: str = Field(..., min_length=1)


class HasRelationshipCondition(BaseModel):
    """Test whether W contains edges of a specific type.  @verified 0000000"""
    test: Literal['has_relationship']
    type: str = Field(..., min_length=1)


Condition = Union[
    HasResultsCondition,
    EmptyCondition,
    CountGteCondition,
    CountLteCondition,
    HasOntologyCondition,
    HasRelationshipCondition,
]
"""Discriminated union of all condition types for ConditionalOp.  @verified 0000000"""


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

class CypherOp(BaseModel):
    """
    Execute a read-only openCypher query against the source graph H.

    The query string is validated for write keywords (V010-V016) before execution.
    An optional ``limit`` field caps the result set independently of any LIMIT
    clause in the Cypher text.

    @verified 0000000
    """
    type: Literal['cypher']
    query: str = Field(..., min_length=1)
    limit: Optional[int] = Field(None, gt=0)


class ApiOp(BaseModel):
    """
    Call a REST API endpoint (smart block).

    The endpoint must be in ``API_ENDPOINT_ALLOWLIST`` (V020). Required parameters
    for that endpoint must be present in ``params`` (V021). Unknown parameters
    produce a warning (V022) but do not block validation.

    @verified 0000000
    """
    type: Literal['api']
    endpoint: str = Field(..., min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict)


class ConditionalOp(BaseModel):
    """
    Conditional branching based on working graph W state.

    Selects which statements to execute based on a ``Condition``. The ``then``
    branch executes when the condition is true; the optional ``else`` branch
    executes otherwise. Nesting depth is limited to ``MAX_NESTING_DEPTH`` (V007).

    @verified 0000000
    """
    type: Literal['conditional']
    condition: Condition
    then: List['Statement'] = Field(..., min_length=1)
    else_: Optional[List['Statement']] = Field(None, alias='else')

    model_config = {'populate_by_name': True}


Operation = Union[CypherOp, ApiOp, ConditionalOp]
"""Discriminated union of all operation types, dispatched on ``type``.  @verified 0000000"""


# ---------------------------------------------------------------------------
# Block annotations (decompilation support)
# ---------------------------------------------------------------------------

class BlockAnnotation(BaseModel):
    """
    Source block type and params for round-trip decompilation.

    When the block editor compiles to the AST, it annotates each statement with
    the originating block type and its parameters. This enables AST-to-blocks
    round-trip.

    @verified 0000000
    """
    blockType: str = Field(..., min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Statement
# ---------------------------------------------------------------------------

class Statement(BaseModel):
    """
    A single step in a GraphProgram.

    Combines a set-algebra operator (``op``) with a typed operation. An optional
    ``label`` provides a human-readable step description. An optional ``block``
    annotation enables decompilation back to the visual block editor.

    @verified 0000000
    """
    op: Operator
    operation: Operation = Field(..., discriminator='type')
    label: Optional[str] = None
    block: Optional[BlockAnnotation] = None


# ---------------------------------------------------------------------------
# Metadata and parameters
# ---------------------------------------------------------------------------

class ProgramMetadata(BaseModel):
    """
    Program-level metadata.

    All fields are optional. ``author`` identifies the originator category
    (human, agent, or system).

    @verified 0000000
    """
    name: Optional[str] = None
    description: Optional[str] = None
    author: Optional[Literal['human', 'agent', 'system']] = None
    created: Optional[str] = None


class ParamDeclaration(BaseModel):
    """
    A program parameter declaration.

    Parameter names must be valid identifiers (letter or underscore, followed by
    alphanumerics or underscores). Only ``string`` and ``number`` types are
    supported. An optional ``default`` provides a fallback when the parameter is
    not supplied at execution time.

    @verified 0000000
    """
    name: str = Field(..., min_length=1, pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    type: Literal['string', 'number']
    default: Optional[Union[str, int, float]] = None


# ---------------------------------------------------------------------------
# GraphProgram (top-level)
# ---------------------------------------------------------------------------

class GraphProgram(BaseModel):
    """
    The canonical AST for a graph query program (ADR-500).

    A finite, bounded sequence of set-algebraic operations over openCypher
    queries and REST API calls. The JSON AST is the single source of truth;
    text DSL, block diagrams, and recorded explorations compile to it.

    Invariants enforced by the type system:
    - ``version`` must be exactly 1
    - ``statements`` must contain at least one entry

    Additional invariants enforced by the validator:
    - V004: parameter names must be unique
    - V006: total operation count <= MAX_STATEMENTS
    - V007: conditional nesting depth <= MAX_NESTING_DEPTH
    - V010-V016: Cypher queries must not contain write keywords
    - V020-V022: API endpoints must be in the allowlist

    @verified 0000000
    """
    version: int = Field(..., ge=1, le=1)
    metadata: ProgramMetadata = Field(default_factory=ProgramMetadata)
    params: Optional[List[ParamDeclaration]] = None
    statements: List[Statement] = Field(..., min_length=1)


# Rebuild models to resolve forward references
ConditionalOp.model_rebuild()
Statement.model_rebuild()


# ---------------------------------------------------------------------------
# API request/response models (ADR-500 Phase 2b)
# ---------------------------------------------------------------------------

class ProgramSubmission(BaseModel):
    """
    Request body for POST /programs and POST /programs/validate.

    Wraps the raw program JSON with an optional name. The ``program`` field
    is Dict (not GraphProgram) because deserialization is handled by the
    validator, which produces structured errors on malformed input rather
    than Pydantic's generic 422 response.

    @verified 0000000
    """
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    program: Dict[str, Any]


class ProgramCreateResponse(BaseModel):
    """
    Response from POST /programs (notarize + store).

    Returns the notarized program alongside its storage ID and validation
    result. ``valid`` is always True on 201 responses (invalid programs
    return 400 instead).

    @verified 0000000
    """
    id: int
    name: str
    program: GraphProgram
    valid: bool = True
    created_at: str
    updated_at: str


class ProgramReadResponse(BaseModel):
    """
    Response from GET /programs/{id}.

    @verified 0000000
    """
    id: int
    name: str
    program: GraphProgram
    owner_id: Optional[int] = None
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Execution models (ADR-500 Phase 3)
# ---------------------------------------------------------------------------

class RawNode(BaseModel):
    """A node in the WorkingGraph, identity-keyed by concept_id."""
    concept_id: str
    label: str = ""
    ontology: Optional[str] = None
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class RawLink(BaseModel):
    """A link in the WorkingGraph, identity-keyed by (from_id, relationship_type, to_id)."""
    from_id: str
    to_id: str
    relationship_type: str
    category: Optional[str] = None
    confidence: Optional[float] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class WorkingGraph(BaseModel):
    """The mutable in-memory graph built during program execution."""
    nodes: List[RawNode] = Field(default_factory=list)
    links: List[RawLink] = Field(default_factory=list)


class StepLogEntry(BaseModel):
    """Per-statement execution log record."""
    statement: int
    op: Operator
    operation_type: Literal['cypher', 'api', 'conditional']
    branch_taken: Optional[Literal['then', 'else']] = None
    nodes_affected: int
    links_affected: int
    w_size: Dict[str, int]
    duration_ms: float


class ProgramResult(BaseModel):
    """Complete execution result from POST /programs/execute."""
    result: WorkingGraph
    log: List[StepLogEntry] = Field(default_factory=list)
    aborted: Optional[Dict[str, Any]] = None


class DeckEntry(BaseModel):
    """A single entry in a program chain (deck). Exactly one of program_id or program required."""
    program_id: Optional[int] = None
    program: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Union[str, int, float]]] = None

    @model_validator(mode='after')
    def check_exactly_one_source(self) -> 'DeckEntry':
        has_id = self.program_id is not None
        has_program = self.program is not None
        if not has_id and not has_program:
            raise ValueError('Each deck entry must provide either program_id or program')
        if has_id and has_program:
            raise ValueError('Deck entry cannot have both program_id and program')
        return self


class ProgramExecuteRequest(BaseModel):
    """
    Request body for POST /programs/execute.

    Single mode: exactly one of program_id or program must be provided.
    Chain mode: provide a deck array of DeckEntry items.
    The two modes are mutually exclusive.
    """
    program_id: Optional[int] = None
    program: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Union[str, int, float]]] = None
    deck: Optional[List['DeckEntry']] = None

    @model_validator(mode='after')
    def check_mode_exclusivity(self) -> 'ProgramExecuteRequest':
        has_id = self.program_id is not None
        has_program = self.program is not None
        has_deck = self.deck is not None
        if has_deck and (has_id or has_program):
            raise ValueError('Cannot combine deck with program_id or program')
        if not has_deck and not has_id and not has_program:
            raise ValueError('Must provide program_id, program, or deck')
        if has_id and has_program:
            raise ValueError('Cannot provide both program_id and program')
        return self


class BatchProgramResult(BaseModel):
    """Result from chained program execution (deck mode)."""
    result: WorkingGraph
    programs: List[ProgramResult] = Field(default_factory=list)
    aborted: Optional[Dict[str, Any]] = None


class ProgramListItem(BaseModel):
    """Lightweight program summary for list endpoints."""
    id: int
    name: str
    description: Optional[str] = None
    statement_count: int
    created_at: str
