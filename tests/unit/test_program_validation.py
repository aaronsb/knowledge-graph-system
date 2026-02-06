"""
GraphProgram Validation Tests (ADR-500)

Executable language specification for GraphProgram validation.
Each test exercises one validation rule from the catalog and references
the rule ID in its docstring for traceability.

These tests run WITHOUT Docker, database, or API server. They test pure
Python validation logic against the AST models -- deserialization, structural
checks, safety checks.

Run:
    pytest tests/unit/test_program_validation.py -v

@verified 0000000
"""

import pytest
from pydantic import ValidationError

from api.app.models.program import (
    GraphProgram,
    Statement,
    CypherOp,
    ApiOp,
    ConditionalOp,
    BlockAnnotation,
    ProgramMetadata,
    ParamDeclaration,
    VALID_OPERATORS,
    CYPHER_WRITE_KEYWORDS,
    API_ENDPOINT_ALLOWLIST,
    MAX_STATEMENTS,
    MAX_NESTING_DEPTH,
    MAX_VARIABLE_PATH_LENGTH,
)
from api.app.services.program_validator import (
    validate_program,
    ValidationResult,
    ValidationIssue,
    _count_operations,
    _max_nesting_depth,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _minimal_program(**overrides) -> dict:
    """Build a minimal valid program dict for testing.  @verified 0000000"""
    base = {
        'version': 1,
        'metadata': {'name': 'Test Program'},
        'statements': [
            {
                'op': '+',
                'operation': {
                    'type': 'cypher',
                    'query': "MATCH (c:Concept) RETURN c LIMIT 10",
                },
            }
        ],
    }
    base.update(overrides)
    return base


def _cypher_stmt(query: str, op: str = '+') -> dict:
    """Build a Cypher statement dict.  @verified 0000000"""
    return {'op': op, 'operation': {'type': 'cypher', 'query': query}}


def _api_stmt(endpoint: str, params: dict = None, op: str = '+') -> dict:
    """Build an API statement dict.  @verified 0000000"""
    return {'op': op, 'operation': {'type': 'api', 'endpoint': endpoint, 'params': params or {}}}


def _conditional_stmt(
    condition: dict,
    then: list,
    else_: list = None,
    op: str = '?',
) -> dict:
    """Build a conditional statement dict.  @verified 0000000"""
    stmt = {
        'op': op,
        'operation': {
            'type': 'conditional',
            'condition': condition,
            'then': then,
        },
    }
    if else_ is not None:
        stmt['operation']['else'] = else_
    return stmt


def _find_issue(result: ValidationResult, rule_id: str) -> ValidationIssue | None:
    """Find a validation issue by rule ID in errors or warnings.  @verified 0000000"""
    for issue in result.errors + result.warnings:
        if issue.rule_id == rule_id:
            return issue
    return None


def _has_error(result: ValidationResult, rule_id: str) -> bool:
    """Check if result contains an error with the given rule ID.  @verified 0000000"""
    return any(e.rule_id == rule_id for e in result.errors)


def _has_warning(result: ValidationResult, rule_id: str) -> bool:
    """Check if result contains a warning with the given rule ID.  @verified 0000000"""
    return any(w.rule_id == rule_id for w in result.warnings)


# ===========================================================================
# Happy Path: Valid Programs
# ===========================================================================

class TestValidPrograms:
    """Verify that well-formed programs pass all validation layers.  @verified 0000000"""

    def test_minimal_program(self):
        """Happy path: single Cypher + operator passes all layers.  @verified 0000000"""
        result = validate_program(_minimal_program())
        assert result.valid is True
        assert result.errors == []

    def test_all_operators(self):
        """V003: all five operators (+, -, &, ?, !) are accepted.  @verified 0000000"""
        for op in VALID_OPERATORS:
            prog = _minimal_program(statements=[_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10", op=op)])
            result = validate_program(prog)
            assert result.valid is True, f"Operator '{op}' should be valid"

    def test_multi_statement_program(self):
        """Happy path: program with multiple heterogeneous statements passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10"),
            _cypher_stmt("MATCH (c:Concept) WHERE c.grounding_strength < 0.2 RETURN c", op='-'),
            _api_stmt('/search/concepts', {'query': 'test', 'min_similarity': 0.7}),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_program_with_params(self):
        """V004: program with unique parameter declarations passes.  @verified 0000000"""
        prog = _minimal_program(params=[
            {'name': 'concept_name', 'type': 'string', 'default': 'test'},
            {'name': 'min_score', 'type': 'number', 'default': 0.5},
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_program_with_block_annotation(self):
        """Happy path: statement with block annotation passes.  @verified 0000000"""
        stmt = _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10")
        stmt['block'] = {'blockType': 'search', 'params': {'query': 'test'}}
        prog = _minimal_program(statements=[stmt])
        result = validate_program(prog)
        assert result.valid is True

    def test_program_with_label(self):
        """Happy path: statement with human-readable label passes.  @verified 0000000"""
        stmt = _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10")
        stmt['label'] = 'Find matching concepts'
        prog = _minimal_program(statements=[stmt])
        result = validate_program(prog)
        assert result.valid is True

    def test_program_with_conditional(self):
        """Happy path: program with conditional branching passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10"),
            _conditional_stmt(
                condition={'test': 'has_results'},
                then=[_cypher_stmt("MATCH (c:Concept)-[r]-(n) RETURN c, r, n LIMIT 50")],
                else_=[_api_stmt('/search/concepts', {'query': 'fallback'})],
            ),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_program_with_all_condition_types(self):
        """V000: each condition test type deserializes and validates.  @verified 0000000"""
        conditions = [
            {'test': 'has_results'},
            {'test': 'empty'},
            {'test': 'count_gte', 'value': 5},
            {'test': 'count_lte', 'value': 100},
            {'test': 'has_ontology', 'ontology': 'philosophy'},
            {'test': 'has_relationship', 'type': 'SUPPORTS'},
        ]
        for cond in conditions:
            prog = _minimal_program(statements=[
                _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10"),
                _conditional_stmt(condition=cond, then=[
                    _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5"),
                ]),
            ])
            result = validate_program(prog)
            assert result.valid is True, f"Condition {cond['test']} should be valid"

    def test_all_allowed_api_endpoints(self):
        """V020/V021/V023: every allowlisted endpoint passes with correctly-typed required params.  @verified 0000000"""
        # Type-appropriate default values for V023 compliance
        _type_defaults = {str: 'test_value', int: 0, float: 0.0, bool: False, list: []}
        for endpoint, spec in API_ENDPOINT_ALLOWLIST.items():
            params = {}
            types = spec.get('types', {})
            for p in spec['required']:
                expected = types.get(p, str)
                if isinstance(expected, tuple):
                    expected = expected[0]
                params[p] = _type_defaults.get(expected, 'test_value')
            prog = _minimal_program(statements=[_api_stmt(endpoint, params)])
            result = validate_program(prog)
            assert result.valid is True, f"Endpoint '{endpoint}' should be valid: {result.errors}"

    def test_program_with_metadata(self):
        """V000: full metadata fields pass deserialization.  @verified 0000000"""
        prog = _minimal_program(metadata={
            'name': 'My Query',
            'description': 'Explores organizational patterns',
            'author': 'human',
            'created': '2026-02-05T12:00:00Z',
        })
        result = validate_program(prog)
        assert result.valid is True

    def test_cypher_with_limit_field(self):
        """V000: CypherOp with explicit limit field passes deserialization.  @verified 0000000"""
        prog = _minimal_program(statements=[{
            'op': '+',
            'operation': {'type': 'cypher', 'query': 'MATCH (c:Concept) RETURN c', 'limit': 50},
        }])
        result = validate_program(prog)
        assert result.valid is True


# ===========================================================================
# Layer 1: Deserialization -- V000
# ===========================================================================

class TestLayer1Deserialization:
    """V000: Pydantic deserialization rejects malformed input.  @verified 0000000"""

    def test_v000_not_a_dict(self):
        """V000: non-dict input is rejected.  @verified 0000000"""
        result = validate_program("not a dict")
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_not_a_dict_list(self):
        """V000: list input is rejected.  @verified 0000000"""
        result = validate_program([1, 2, 3])
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_none_input(self):
        """V000: None input is rejected.  @verified 0000000"""
        result = validate_program(None)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_empty_dict(self):
        """V000: empty dict is rejected (missing required fields).  @verified 0000000"""
        result = validate_program({})
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_missing_version(self):
        """V000: missing version field is rejected.  @verified 0000000"""
        prog = _minimal_program()
        del prog['version']
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_missing_statements(self):
        """V000: missing statements field is rejected.  @verified 0000000"""
        prog = _minimal_program()
        del prog['statements']
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_wrong_version_type(self):
        """V000: string version is rejected (must be int).  @verified 0000000"""
        result = validate_program(_minimal_program(version='one'))
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_empty_statements_list(self):
        """V000: empty statements list is rejected (min_length=1).  @verified 0000000"""
        result = validate_program(_minimal_program(statements=[]))
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_invalid_operator(self):
        """V000: unknown operator value '*' is rejected by Literal type.  @verified 0000000"""
        prog = _minimal_program(statements=[
            {'op': '*', 'operation': {'type': 'cypher', 'query': 'MATCH (c:Concept) RETURN c'}},
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_invalid_operation_type(self):
        """V000: unknown operation type 'unknown' is rejected by discriminator.  @verified 0000000"""
        prog = _minimal_program(statements=[
            {'op': '+', 'operation': {'type': 'unknown', 'query': 'something'}},
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_cypher_empty_query(self):
        """V000: empty Cypher query string is rejected (min_length=1).  @verified 0000000"""
        prog = _minimal_program(statements=[
            {'op': '+', 'operation': {'type': 'cypher', 'query': ''}},
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_invalid_param_name(self):
        """V000: parameter name with spaces is rejected by pattern.  @verified 0000000"""
        prog = _minimal_program(params=[
            {'name': 'bad name', 'type': 'string'},
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_invalid_param_type(self):
        """V000: unknown parameter type 'boolean' is rejected by Literal.  @verified 0000000"""
        prog = _minimal_program(params=[
            {'name': 'x', 'type': 'boolean'},
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_invalid_author(self):
        """V000: unknown author value 'robot' is rejected by Literal.  @verified 0000000"""
        prog = _minimal_program(metadata={'author': 'robot'})
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_invalid_condition_test(self):
        """V000: unknown condition test type is rejected by union discriminator.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _conditional_stmt(
                condition={'test': 'invalid_test'},
                then=[_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")],
            ),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_count_gte_zero(self):
        """V000: count_gte with value=0 is rejected (gt=0 constraint).  @verified 0000000"""
        prog = _minimal_program(statements=[
            _conditional_stmt(
                condition={'test': 'count_gte', 'value': 0},
                then=[_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")],
            ),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_limit_zero(self):
        """V000: CypherOp with limit=0 is rejected (gt=0 constraint).  @verified 0000000"""
        prog = _minimal_program(statements=[{
            'op': '+',
            'operation': {'type': 'cypher', 'query': 'MATCH (c:Concept) RETURN c', 'limit': 0},
        }])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')

    def test_v000_limit_negative(self):
        """V000: CypherOp with negative limit is rejected (gt=0 constraint).  @verified 0000000"""
        prog = _minimal_program(statements=[{
            'op': '+',
            'operation': {'type': 'cypher', 'query': 'MATCH (c:Concept) RETURN c', 'limit': -5},
        }])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V000')


# ===========================================================================
# Layer 2: Structural -- V001-V005
# ===========================================================================

class TestLayer2Structural:
    """V001-V005: structural validation beyond Pydantic type checks.  @verified 0000000"""

    def test_v001_wrong_version_value(self):
        """V001: version=2 is rejected (only version 1 supported).  @verified 0000000"""
        # Pydantic enforces ge=1, le=1, so version=2 triggers V000 at Layer 1
        prog = _minimal_program(version=2)
        result = validate_program(prog)
        assert not result.valid

    def test_v004_duplicate_param_names(self):
        """V004: duplicate parameter names are rejected.  @verified 0000000"""
        prog = _minimal_program(params=[
            {'name': 'x', 'type': 'string'},
            {'name': 'x', 'type': 'number'},
        ])
        result = validate_program(prog)
        assert _has_error(result, 'V004')

    def test_v004_unique_param_names_pass(self):
        """V004: unique parameter names pass structural check.  @verified 0000000"""
        prog = _minimal_program(params=[
            {'name': 'x', 'type': 'string'},
            {'name': 'y', 'type': 'number'},
        ])
        result = validate_program(prog)
        assert not _has_error(result, 'V004')


# ===========================================================================
# Layer 3: Safety -- Cypher Write Keywords V010-V016
# ===========================================================================

class TestCypherWriteKeywords:
    """V010-V016: Cypher queries must not contain write keywords.  @verified 0000000"""

    def test_v010_create(self):
        """V010: CREATE keyword in Cypher query is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("CREATE (c:Concept {label: 'test'})"),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V010')

    def test_v011_set(self):
        """V011: SET keyword in Cypher query is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) SET c.label = 'new'"),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V011')

    def test_v012_delete(self):
        """V012: DELETE keyword in Cypher query is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) DELETE c"),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V012')

    def test_v013_merge(self):
        """V013: MERGE keyword in Cypher query is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MERGE (c:Concept {label: 'test'})"),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V013')

    def test_v014_remove(self):
        """V014: REMOVE keyword in Cypher query is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) REMOVE c.label"),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V014')

    def test_v015_drop(self):
        """V015: DROP keyword in Cypher query is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("DROP INDEX concept_label_idx"),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V015')

    def test_v016_detach(self):
        """V016: DETACH keyword in Cypher query is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) DETACH DELETE c"),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V016')

    def test_v010_v016_case_insensitive(self):
        """V010-V016: write keyword detection is case-insensitive.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("match (c:Concept) set c.label = 'x'"),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V011')

    def test_v010_v016_string_literal_excluded(self):
        """V010-V016: write keywords inside string literals are not flagged.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) WHERE c.label = 'CREATE something' RETURN c LIMIT 10"),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v010_v016_comment_excluded(self):
        """V010-V016: write keywords inside comments are not flagged.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10 -- CREATE is just a comment"),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v010_word_boundary(self):
        """V010: substring 'CREATED' does not trigger CREATE detection.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) WHERE c.created_at > '2025-01-01' RETURN c LIMIT 10"),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v010_v016_read_only_queries_pass(self):
        """V010-V016: standard read-only queries pass all safety checks.  @verified 0000000"""
        queries = [
            "MATCH (c:Concept)-[r]-(n:Concept) RETURN c, r, n LIMIT 50",
            "MATCH (c:Concept) WHERE c.label CONTAINS 'test' RETURN c LIMIT 10",
            "MATCH (c:Concept) RETURN count(c) as total",
            "MATCH path = (a:Concept)-[*..3]-(b:Concept) WHERE a.label = 'X' RETURN path LIMIT 5",
        ]
        for query in queries:
            prog = _minimal_program(statements=[_cypher_stmt(query)])
            result = validate_program(prog)
            assert result.valid is True, f"Query should pass: {query[:40]}..."

    def test_v010_v011_v012_multiple_keywords(self):
        """V010/V011/V012: multiple write keywords in one query produce multiple errors.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("CREATE (c:Concept) SET c.label = 'x' DELETE c"),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V010')  # CREATE
        assert _has_error(result, 'V011')  # SET
        assert _has_error(result, 'V012')  # DELETE

    def test_v010_nested_in_conditional(self):
        """V010: Cypher inside conditional branches is safety-checked.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _conditional_stmt(
                condition={'test': 'has_results'},
                then=[_cypher_stmt("CREATE (c:Concept {label: 'x'})")],
            ),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V010')


# ===========================================================================
# Layer 3: Safety -- API Endpoint Allowlist V020-V022
# ===========================================================================

class TestApiEndpointSafety:
    """V020-V022: API operations must use allowed endpoints with correct params.  @verified 0000000"""

    def test_v020_disallowed_endpoint(self):
        """V020: endpoint not in allowlist is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/admin/delete-everything', {}),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V020')

    def test_v020_path_traversal_rejected(self):
        """V020: path traversal attempt is rejected by allowlist.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/../../../etc/passwd', {}),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V020')

    def test_v021_missing_required_param(self):
        """V021: missing required parameter is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {}),  # missing 'query'
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V021')

    def test_v021_required_param_present(self):
        """V021: required parameter present passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 'test'}),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v022_unknown_param_warning(self):
        """V022: unknown parameter produces warning, not error.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 'test', 'bogus_param': True}),
        ])
        result = validate_program(prog)
        assert result.valid is True  # Warnings don't block
        assert _has_warning(result, 'V022')

    def test_v021_batch_endpoint_requires_concept_ids(self):
        """V021: /concepts/batch requires concept_ids parameter.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/concepts/batch', {}),
        ])
        result = validate_program(prog)
        assert not result.valid
        assert _has_error(result, 'V021')

    def test_v020_v021_all_optional_params(self):
        """V020/V021: endpoint with all optional params passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {
                'query': 'test',
                'min_similarity': 0.7,
                'limit': 10,
                'ontology': 'my-ontology',
                'offset': 0,
            }),
        ])
        result = validate_program(prog)
        assert result.valid is True


# ===========================================================================
# Layer 3: Safety -- API Parameter Types V023
# ===========================================================================

class TestApiParameterTypes:
    """V023: API endpoint parameter type enforcement.  @verified 0000000"""

    def test_v023_string_param_correct_type(self):
        """V023: string parameter with string value passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 'machine learning'}),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v023_numeric_param_int(self):
        """V023: numeric parameter accepts int.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 'test', 'limit': 10}),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v023_numeric_param_float(self):
        """V023: min_similarity accepts float.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 'test', 'min_similarity': 0.7}),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v023_string_param_wrong_type_int(self):
        """V023: string parameter with int value is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 123}),
        ])
        result = validate_program(prog)
        assert result.valid is False
        assert _has_error(result, 'V023')

    def test_v023_int_param_wrong_type_string(self):
        """V023: int parameter with string value is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 'test', 'limit': 'ten'}),
        ])
        result = validate_program(prog)
        assert result.valid is False
        assert _has_error(result, 'V023')

    def test_v023_bool_param_correct_type(self):
        """V023: bool parameter with bool value passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/concepts/details', {'concept_id': 'c_123', 'include_diversity': True}),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v023_bool_param_wrong_type(self):
        """V023: bool parameter with string value is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/concepts/details', {'concept_id': 'c_123', 'include_diversity': 'yes'}),
        ])
        result = validate_program(prog)
        assert result.valid is False
        assert _has_error(result, 'V023')

    def test_v023_list_param_correct_type(self):
        """V023: list parameter with list value passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/concepts/batch', {'concept_ids': ['c_1', 'c_2']}),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v023_list_param_wrong_type(self):
        """V023: list parameter with string value is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/concepts/batch', {'concept_ids': 'c_1'}),
        ])
        result = validate_program(prog)
        assert result.valid is False
        assert _has_error(result, 'V023')

    def test_v023_error_message_includes_types(self):
        """V023: error message names expected and actual types.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 42}),
        ])
        result = validate_program(prog)
        error = _find_issue(result, 'V023')
        assert error is not None
        assert 'str' in error.message
        assert 'int' in error.message

    def test_v023_unknown_params_skip_type_check(self):
        """V023: unknown params get V022 warning, not V023 type error.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 'test', 'bogus': 999}),
        ])
        result = validate_program(prog)
        assert result.valid is True  # unknown params are warnings only
        assert _has_warning(result, 'V022')
        assert not _has_error(result, 'V023')


# ===========================================================================
# Layer 3: Safety -- Variable-Length Path Bounds V030
# ===========================================================================

class TestVariableLengthPaths:
    """V030: variable-length Cypher path bounds.  @verified 0000000"""

    def test_v030_unbounded_star(self):
        """V030: [*] (fully unbounded) is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[*]->(b:Concept) RETURN a, b"),
        ])
        result = validate_program(prog)
        assert result.valid is False
        assert _has_error(result, 'V030')

    def test_v030_no_upper_bound(self):
        """V030: [*2..] (no upper bound) is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[*2..]->(b:Concept) RETURN a, b"),
        ])
        result = validate_program(prog)
        assert result.valid is False
        assert _has_error(result, 'V030')

    def test_v030_no_upper_bound_dot_only(self):
        """V030: [*..] (no bounds at all, range syntax) is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[*..]->(b:Concept) RETURN a, b"),
        ])
        result = validate_program(prog)
        assert result.valid is False
        assert _has_error(result, 'V030')

    def test_v030_exceeds_max_depth(self):
        """V030: [*1..10] exceeding MAX_VARIABLE_PATH_LENGTH is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[*1..10]->(b:Concept) RETURN a, b"),
        ])
        result = validate_program(prog)
        assert result.valid is False
        assert _has_error(result, 'V030')

    def test_v030_within_bounds(self):
        """V030: [*1..3] within MAX_VARIABLE_PATH_LENGTH passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[*1..3]->(b:Concept) RETURN a, b"),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v030_exact_at_max(self):
        """V030: [*1..6] at exactly MAX_VARIABLE_PATH_LENGTH passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[*1..6]->(b:Concept) RETURN a, b"),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v030_fixed_depth_within_bounds(self):
        """V030: [*3] (fixed-length) within bounds passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[*3]->(b:Concept) RETURN a, b"),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v030_fixed_depth_exceeds_bounds(self):
        """V030: [*10] (fixed-length) exceeding bounds is rejected.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[*10]->(b:Concept) RETURN a, b"),
        ])
        result = validate_program(prog)
        assert result.valid is False
        assert _has_error(result, 'V030')

    def test_v030_no_variable_path(self):
        """V030: normal relationship traversal (no [*]) passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[r]->(b:Concept) RETURN a, r, b"),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v030_upper_bound_only(self):
        """V030: [*..3] (upper bound only) within limits passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[*..3]->(b:Concept) RETURN a, b"),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v030_error_message_includes_path(self):
        """V030: error message includes the offending path expression.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (a:Concept)-[*1..10]->(b:Concept) RETURN a, b"),
        ])
        result = validate_program(prog)
        error = _find_issue(result, 'V030')
        assert error is not None
        assert '*1..10' in error.message


# ===========================================================================
# Layer 3: Safety -- Statement Bounds V006, Nesting Depth V007
# ===========================================================================

class TestBoundsAndNesting:
    """V006/V007: operation count and nesting depth limits.  @verified 0000000"""

    def test_v006_within_bounds(self):
        """V006: program at MAX_STATEMENTS count passes.  @verified 0000000"""
        stmts = [_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10")] * MAX_STATEMENTS
        prog = _minimal_program(statements=stmts)
        result = validate_program(prog)
        assert not _has_error(result, 'V006')

    def test_v006_exceeds_bounds(self):
        """V006: program exceeding MAX_STATEMENTS is rejected.  @verified 0000000"""
        stmts = [_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10")] * (MAX_STATEMENTS + 1)
        prog = _minimal_program(statements=stmts)
        result = validate_program(prog)
        assert _has_error(result, 'V006')

    def test_v007_nesting_at_max(self):
        """V007: nesting at exactly MAX_NESTING_DEPTH passes.  @verified 0000000"""
        inner = [_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")]
        for _ in range(MAX_NESTING_DEPTH):
            inner = [_conditional_stmt(condition={'test': 'has_results'}, then=inner)]
        prog = _minimal_program(statements=inner)
        result = validate_program(prog)
        assert not _has_error(result, 'V007')

    def test_v007_nesting_exceeds_max(self):
        """V007: nesting beyond MAX_NESTING_DEPTH is rejected.  @verified 0000000"""
        inner = [_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")]
        for _ in range(MAX_NESTING_DEPTH + 1):
            inner = [_conditional_stmt(condition={'test': 'has_results'}, then=inner)]
        prog = _minimal_program(statements=inner)
        result = validate_program(prog)
        assert _has_error(result, 'V007')

    def test_v006_conditional_counts_longer_path(self):
        """V006: operation count uses the longer branch of conditionals.  @verified 0000000"""
        then_branch = [_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")] * 3
        else_branch = [_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")] * 5
        prog = _minimal_program(statements=[
            _conditional_stmt(
                condition={'test': 'has_results'},
                then=then_branch,
                else_=else_branch,
            ),
        ])
        program = GraphProgram.model_validate(prog)
        assert _count_operations(program.statements) == 5


# ===========================================================================
# Edge Cases
# ===========================================================================

class TestEdgeCases:
    """Edge cases exercising boundary conditions and error response format.  @verified 0000000"""

    def test_single_statement_program(self):
        """V002: program with exactly one statement passes minimum check.  @verified 0000000"""
        prog = _minimal_program()
        result = validate_program(prog)
        assert result.valid is True

    def test_conditional_without_else(self):
        """V005: conditional with then but no else passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10"),
            _conditional_stmt(
                condition={'test': 'empty'},
                then=[_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")],
            ),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_mixed_operation_types(self):
        """Happy path: Cypher, API, and conditional mixed in one program.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10"),
            _api_stmt('/search/concepts', {'query': 'test'}),
            _conditional_stmt(
                condition={'test': 'count_gte', 'value': 5},
                then=[_cypher_stmt("MATCH (c:Concept)-[r]-(n) RETURN c, r, n LIMIT 50")],
                else_=[_api_stmt('/search/sources', {'query': 'fallback'})],
            ),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v000_param_name_with_underscore(self):
        """V000: parameter names with leading underscores pass pattern check.  @verified 0000000"""
        prog = _minimal_program(params=[
            {'name': '_private', 'type': 'string'},
            {'name': 'my_param_123', 'type': 'number'},
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v000_param_name_starting_with_digit_rejected(self):
        """V000: parameter names starting with digit are rejected by pattern.  @verified 0000000"""
        prog = _minimal_program(params=[
            {'name': '123abc', 'type': 'string'},
        ])
        result = validate_program(prog)
        assert not result.valid

    def test_error_response_has_statement_index(self):
        """V010: error references correct 0-based statement index.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10"),
            _cypher_stmt("CREATE (c:Concept {label: 'evil'})"),
        ])
        result = validate_program(prog)
        assert not result.valid
        issue = _find_issue(result, 'V010')
        assert issue is not None
        assert issue.statement == 1  # Second statement (0-indexed)

    def test_error_response_has_field_path(self):
        """V010: error includes dot-separated field path.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _cypher_stmt("CREATE (c:Concept)"),
        ])
        result = validate_program(prog)
        issue = _find_issue(result, 'V010')
        assert issue is not None
        assert issue.field == 'operation.query'

    def test_v022_warnings_dont_block_validation(self):
        """V022: programs with warnings but no errors are still valid.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 'test', 'unknown_field': True}),
        ])
        result = validate_program(prog)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert len(result.errors) == 0

    def test_no_metadata_defaults_work(self):
        """V000: program with no explicit metadata uses Pydantic defaults.  @verified 0000000"""
        prog = {'version': 1, 'statements': [
            _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10"),
        ]}
        result = validate_program(prog)
        assert result.valid is True

    def test_v021_vocabulary_status_no_required_params(self):
        """V021: /vocabulary/status has no required params, empty dict passes.  @verified 0000000"""
        prog = _minimal_program(statements=[
            _api_stmt('/vocabulary/status', {}),
        ])
        result = validate_program(prog)
        assert result.valid is True

    def test_v000_api_params_defaults_empty(self):
        """V000: ApiOp with no params field defaults to empty dict.  @verified 0000000"""
        prog = _minimal_program(statements=[{
            'op': '+',
            'operation': {'type': 'api', 'endpoint': '/vocabulary/status'},
        }])
        result = validate_program(prog)
        assert result.valid is True


# ===========================================================================
# Pydantic Model Unit Tests (direct model construction)
# ===========================================================================

class TestPydanticModels:
    """Direct Pydantic model construction and discriminator dispatch.  @verified 0000000"""

    def test_graph_program_model_validate(self):
        """V000: GraphProgram.model_validate succeeds with valid dict.  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program())
        assert prog.version == 1
        assert len(prog.statements) == 1
        assert prog.statements[0].op == '+'

    def test_graph_program_rejects_invalid(self):
        """V000: GraphProgram.model_validate raises on empty statements.  @verified 0000000"""
        with pytest.raises(ValidationError):
            GraphProgram.model_validate({'version': 1, 'statements': []})

    def test_statement_discriminator_cypher(self):
        """V000: operation discriminator resolves CypherOp via type='cypher'.  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program())
        assert isinstance(prog.statements[0].operation, CypherOp)

    def test_statement_discriminator_api(self):
        """V000: operation discriminator resolves ApiOp via type='api'.  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program(statements=[
            _api_stmt('/search/concepts', {'query': 'test'}),
        ]))
        assert isinstance(prog.statements[0].operation, ApiOp)
        assert prog.statements[0].operation.endpoint == '/search/concepts'

    def test_statement_discriminator_conditional(self):
        """V000: operation discriminator resolves ConditionalOp via type='conditional'.  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program(statements=[
            _conditional_stmt(
                condition={'test': 'has_results'},
                then=[_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")],
            ),
        ]))
        op = prog.statements[0].operation
        assert isinstance(op, ConditionalOp)
        assert len(op.then) == 1
        assert isinstance(op.then[0].operation, CypherOp)

    def test_conditional_else_branch_parsed(self):
        """V000: ConditionalOp else branch is deserialized correctly.  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program(statements=[
            _conditional_stmt(
                condition={'test': 'empty'},
                then=[_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")],
                else_=[_api_stmt('/search/concepts', {'query': 'fallback'})],
            ),
        ]))
        op = prog.statements[0].operation
        assert isinstance(op, ConditionalOp)
        assert op.else_ is not None
        assert len(op.else_) == 1
        assert isinstance(op.else_[0].operation, ApiOp)

    def test_block_annotation_roundtrip(self):
        """V000: BlockAnnotation is preserved through model_validate.  @verified 0000000"""
        stmt_dict = _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10")
        stmt_dict['block'] = {'blockType': 'search', 'params': {'query': 'org'}}
        prog = GraphProgram.model_validate(_minimal_program(statements=[stmt_dict]))
        assert prog.statements[0].block is not None
        assert prog.statements[0].block.blockType == 'search'
        assert prog.statements[0].block.params['query'] == 'org'

    def test_param_declaration_model(self):
        """V000: ParamDeclaration validates name, type, and default.  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program(params=[
            {'name': 'concept_name', 'type': 'string', 'default': 'test'},
        ]))
        assert prog.params is not None
        assert prog.params[0].name == 'concept_name'
        assert prog.params[0].type == 'string'
        assert prog.params[0].default == 'test'


# ===========================================================================
# Helper Function Unit Tests
# ===========================================================================

class TestHelperFunctions:
    """Unit tests for _count_operations and _max_nesting_depth.  @verified 0000000"""

    def test_count_operations_flat(self):
        """V006: flat statement list counts each statement as 1.  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program(statements=[
            _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10"),
            _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10"),
            _cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 10"),
        ]))
        assert _count_operations(prog.statements) == 3

    def test_count_operations_conditional_takes_max(self):
        """V006: conditional counts the longer branch (max of then vs else).  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program(statements=[
            _conditional_stmt(
                condition={'test': 'has_results'},
                then=[_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")] * 2,
                else_=[_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")] * 4,
            ),
        ]))
        assert _count_operations(prog.statements) == 4

    def test_count_operations_conditional_no_else(self):
        """V006: conditional without else uses then count (else=0).  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program(statements=[
            _conditional_stmt(
                condition={'test': 'has_results'},
                then=[_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")] * 3,
            ),
        ]))
        assert _count_operations(prog.statements) == 3

    def test_max_nesting_depth_flat(self):
        """V007: flat program (no conditionals) has depth 0.  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program())
        assert _max_nesting_depth(prog.statements, 0) == 0

    def test_max_nesting_depth_single_conditional(self):
        """V007: single conditional has nesting depth 1.  @verified 0000000"""
        prog = GraphProgram.model_validate(_minimal_program(statements=[
            _conditional_stmt(
                condition={'test': 'has_results'},
                then=[_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")],
            ),
        ]))
        assert _max_nesting_depth(prog.statements, 0) == 1

    def test_max_nesting_depth_nested(self):
        """V007: doubly-nested conditional has depth 2.  @verified 0000000"""
        inner = [_cypher_stmt("MATCH (c:Concept) RETURN c LIMIT 5")]
        level1 = [_conditional_stmt(condition={'test': 'has_results'}, then=inner)]
        level0 = [_conditional_stmt(condition={'test': 'empty'}, then=level1)]
        prog = GraphProgram.model_validate(_minimal_program(statements=level0))
        assert _max_nesting_depth(prog.statements, 0) == 2
