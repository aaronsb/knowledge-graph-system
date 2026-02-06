"""
GraphProgram Validator (ADR-500)

Validates GraphProgram ASTs through four ordered layers, cheapest first:

  Layer 1 -- Deserialization: Pydantic type checking (malformed JSON, wrong types)
  Layer 2 -- Structural: required fields, non-empty statements, known operators
  Layer 3 -- Safety: write-keyword rejection, endpoint allowlist, statement bounds
  Layer 4 -- Semantic: param resolution, nesting depth, boundedness (future)

The validator produces structured errors referencing statement index and field path.
Errors block execution; warnings are advisory.

Zero platform dependencies: pure Python + Pydantic only. No database, no FastAPI,
no AGE client. Importable and testable from a bare ``pytest`` run without Docker.

Usage:
    from api.app.services.program_validator import validate_program

    result = validate_program(json_data)
    if not result.valid:
        for error in result.errors:
            print(f"[{error.rule_id}] stmt {error.statement}: {error.message}")

@verified 0000000
"""

import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ValidationError

from api.app.models.program import (
    GraphProgram,
    Statement,
    CypherOp,
    ApiOp,
    ConditionalOp,
    CYPHER_WRITE_KEYWORDS,
    API_ENDPOINT_ALLOWLIST,
    MAX_STATEMENTS,
    MAX_NESTING_DEPTH,
    MAX_VARIABLE_PATH_LENGTH,
)


# ---------------------------------------------------------------------------
# Validation result types
# ---------------------------------------------------------------------------

class ValidationIssue(BaseModel):
    """
    A single validation error or warning.

    Attributes:
        rule_id: Catalog rule identifier (e.g. V010).
        severity: 'error' blocks execution; 'warning' is advisory.
        statement: 0-based index into program.statements, or None for program-level.
        field: Dot-separated path to the problematic field.
        message: Human-readable description.

    @verified 0000000
    """
    rule_id: str
    severity: str = Field(default='error')
    statement: Optional[int] = None
    field: Optional[str] = None
    message: str


class ValidationResult(BaseModel):
    """
    Result of validating a GraphProgram.

    ``valid`` is True when ``errors`` is empty. Warnings are advisory and do not
    affect the ``valid`` flag.

    @verified 0000000
    """
    valid: bool
    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Layer 1: Deserialization (Pydantic)
# ---------------------------------------------------------------------------

def _layer1_deserialize(data: Any) -> tuple[Optional[GraphProgram], List[ValidationIssue]]:
    """
    Parse raw data into a GraphProgram via Pydantic.

    All deserialization failures produce rule ID V000. If the program cannot be
    deserialized, returns ``(None, errors)`` and subsequent layers are skipped.

    Args:
        data: Raw JSON-compatible data (expected to be a dict).

    Returns:
        Tuple of (parsed program or None, list of V000 issues).

    @verified 0000000
    """
    issues: List[ValidationIssue] = []

    if not isinstance(data, dict):
        issues.append(ValidationIssue(
            rule_id='V000',
            message='Program must be a JSON object',
        ))
        return None, issues

    try:
        program = GraphProgram.model_validate(data)
        return program, []
    except ValidationError as exc:
        for error in exc.errors():
            loc = '.'.join(str(p) for p in error['loc'])
            issues.append(ValidationIssue(
                rule_id='V000',
                field=loc,
                message=error['msg'],
            ))
        return None, issues


# ---------------------------------------------------------------------------
# Layer 2: Structural validation
# ---------------------------------------------------------------------------

def _layer2_structural(program: GraphProgram) -> List[ValidationIssue]:
    """
    Check structural invariants that Pydantic's type system cannot express.

    Rules checked:
        V001: version must be 1
        V002: statements must be non-empty
        V003: each statement is structurally valid (delegated)
        V004: parameter names must be unique

    Args:
        program: A successfully deserialized GraphProgram.

    Returns:
        List of structural validation issues.

    @verified 0000000
    """
    issues: List[ValidationIssue] = []

    # V001: version must be 1
    if program.version != 1:
        issues.append(ValidationIssue(
            rule_id='V001',
            field='version',
            message=f'Version must be 1, got {program.version}',
        ))

    # V002: statements must be non-empty (already enforced by Pydantic min_length=1,
    # but explicit for completeness)
    if not program.statements:
        issues.append(ValidationIssue(
            rule_id='V002',
            field='statements',
            message='Program must contain at least one statement',
        ))

    # V003: validate each statement structurally
    for i, stmt in enumerate(program.statements):
        issues.extend(_validate_statement_structure(stmt, i))

    # V004: param names must be unique
    if program.params:
        seen_names: set[str] = set()
        for param in program.params:
            if param.name in seen_names:
                issues.append(ValidationIssue(
                    rule_id='V004',
                    field='params',
                    message=f'Duplicate parameter name: {param.name}',
                ))
            seen_names.add(param.name)

    return issues


def _validate_statement_structure(stmt: Statement, index: int) -> List[ValidationIssue]:
    """
    Validate structural properties of a single statement.

    Checks V005 (conditional then-branch non-empty) and recursively validates
    nested statements inside conditionals.

    Args:
        stmt: The statement to validate.
        index: 0-based index of the statement in the program for error reporting.

    Returns:
        List of structural validation issues.

    @verified 0000000
    """
    issues: List[ValidationIssue] = []

    # V003: operator must be one of +/-/&/?/!
    # (already enforced by Pydantic Literal, but kept for the catalog)

    op = stmt.operation
    if isinstance(op, ConditionalOp):
        # V005: conditional must have non-empty 'then' branch
        if not op.then:
            issues.append(ValidationIssue(
                rule_id='V005',
                statement=index,
                field='operation.then',
                message='Conditional must have at least one statement in then branch',
            ))
        # Recursively validate nested statements
        for nested in op.then:
            issues.extend(_validate_statement_structure(nested, index))
        if op.else_:
            for nested in op.else_:
                issues.extend(_validate_statement_structure(nested, index))

    return issues


# ---------------------------------------------------------------------------
# Layer 3: Safety validation
# ---------------------------------------------------------------------------

def _layer3_safety(program: GraphProgram) -> List[ValidationIssue]:
    """
    Check safety constraints that protect the database and system.

    Rules checked:
        V006: total operation count within MAX_STATEMENTS
        V007: conditional nesting depth within MAX_NESTING_DEPTH
        V010-V016: Cypher write-keyword rejection (per statement)
        V020-V023: API endpoint allowlist and param type enforcement (per statement)
        V030: variable-length Cypher path bounds (per statement)

    Args:
        program: A successfully deserialized GraphProgram.

    Returns:
        List of safety validation issues (both errors and warnings).

    @verified 0000000
    """
    issues: List[ValidationIssue] = []

    # V006: total statement count within bounds
    total = _count_operations(program.statements)
    if total > MAX_STATEMENTS:
        issues.append(ValidationIssue(
            rule_id='V006',
            field='statements',
            message=f'Program exceeds maximum operation count ({total} > {MAX_STATEMENTS})',
        ))

    # V007: nesting depth within bounds
    depth = _max_nesting_depth(program.statements, current_depth=0)
    if depth > MAX_NESTING_DEPTH:
        issues.append(ValidationIssue(
            rule_id='V007',
            field='statements',
            message=f'Conditional nesting exceeds maximum depth ({depth} > {MAX_NESTING_DEPTH})',
        ))

    # Per-statement safety checks
    for i, stmt in enumerate(program.statements):
        issues.extend(_validate_statement_safety(stmt, i))

    return issues


def _validate_statement_safety(stmt: Statement, index: int) -> List[ValidationIssue]:
    """
    Validate safety properties of a single statement.

    Dispatches to type-specific safety checks: ``_check_cypher_safety`` for
    CypherOp, ``_check_api_safety`` for ApiOp, and recurses into conditional
    branches for ConditionalOp.

    Args:
        stmt: The statement to validate.
        index: 0-based index for error reporting.

    Returns:
        List of safety validation issues.

    @verified 0000000
    """
    issues: List[ValidationIssue] = []
    op = stmt.operation

    if isinstance(op, CypherOp):
        issues.extend(_check_cypher_safety(op.query, index))
    elif isinstance(op, ApiOp):
        issues.extend(_check_api_safety(op, index))
    elif isinstance(op, ConditionalOp):
        for nested in op.then:
            issues.extend(_validate_statement_safety(nested, index))
        if op.else_:
            for nested in op.else_:
                issues.extend(_validate_statement_safety(nested, index))

    return issues


def _check_cypher_safety(query: str, index: int) -> List[ValidationIssue]:
    """
    Check a Cypher query string for write keywords (V010-V016).

    Detection rules:
    - Case-insensitive (``create`` and ``CREATE`` both trigger).
    - Word-boundary matching (``CREATED`` does not trigger V010).
    - Content inside string literals (``'...'``, ``"..."``) is excluded.
    - Content inside comments (``--``, ``/* */``) is excluded.

    Args:
        query: The Cypher query string from a CypherOp.
        index: Statement index for error reporting.

    Returns:
        List of V010-V016 issues, one per detected write keyword.

    @verified 0000000
    """
    issues: List[ValidationIssue] = []
    upper = query.upper()

    # Remove content inside string literals to avoid false positives
    sanitized = re.sub(r"'[^']*'", '', upper)
    sanitized = re.sub(r'"[^"]*"', '', sanitized)
    # Strip line comments
    sanitized = re.sub(r'--.*$', '', sanitized, flags=re.MULTILINE)
    # Strip block comments
    sanitized = re.sub(r'/\*.*?\*/', '', sanitized, flags=re.DOTALL)

    for keyword in CYPHER_WRITE_KEYWORDS:
        pattern = rf'\b{keyword}\b'
        if re.search(pattern, sanitized):
            rule_id = _cypher_keyword_rule_id(keyword)
            issues.append(ValidationIssue(
                rule_id=rule_id,
                severity='error',
                statement=index,
                field='operation.query',
                message=f'Cypher query contains write keyword: {keyword}',
            ))

    # V030: variable-length path bounds check
    issues.extend(_check_variable_length_paths(query, index))

    return issues


def _cypher_keyword_rule_id(keyword: str) -> str:
    """
    Map a Cypher write keyword to its validation rule ID.

    Args:
        keyword: Uppercase Cypher keyword (e.g. 'CREATE').

    Returns:
        Rule ID string (e.g. 'V010').

    @verified 0000000
    """
    mapping = {
        'CREATE': 'V010',
        'SET': 'V011',
        'DELETE': 'V012',
        'MERGE': 'V013',
        'REMOVE': 'V014',
        'DROP': 'V015',
        'DETACH': 'V016',
    }
    return mapping.get(keyword, 'V010')


def _check_api_safety(op: ApiOp, index: int) -> List[ValidationIssue]:
    """
    Check an API operation against the endpoint allowlist (V020-V023).

    Checks:
    - V020: endpoint must be in API_ENDPOINT_ALLOWLIST.
    - V021: all required parameters for the endpoint must be present.
    - V022: unknown parameters produce a warning (advisory, not blocking).
    - V023: parameter values must match declared types in the allowlist.

    Args:
        op: The ApiOp to validate.
        index: Statement index for error reporting.

    Returns:
        List of V020-V023 issues.

    @verified 0000000
    """
    issues: List[ValidationIssue] = []

    # V020: endpoint must be in allowlist
    if op.endpoint not in API_ENDPOINT_ALLOWLIST:
        issues.append(ValidationIssue(
            rule_id='V020',
            severity='error',
            statement=index,
            field='operation.endpoint',
            message=f'Endpoint not in allowlist: {op.endpoint}',
        ))
        return issues  # Can't check params without knowing the endpoint

    spec = API_ENDPOINT_ALLOWLIST[op.endpoint]

    # V021: required params must be present
    for required_param in spec['required']:
        if required_param not in op.params:
            issues.append(ValidationIssue(
                rule_id='V021',
                severity='error',
                statement=index,
                field=f'operation.params.{required_param}',
                message=f'Required parameter missing: {required_param}',
            ))

    # V022: unknown params are warnings
    known = set(spec['required']) | set(spec['optional'])
    for param_name in op.params:
        if param_name not in known:
            issues.append(ValidationIssue(
                rule_id='V022',
                severity='warning',
                statement=index,
                field=f'operation.params.{param_name}',
                message=f'Unknown parameter: {param_name}',
            ))

    # V023: parameter type enforcement
    type_spec = spec.get('types', {})
    for param_name, param_value in op.params.items():
        if param_name in type_spec:
            expected = type_spec[param_name]
            if not isinstance(param_value, expected):
                # Format expected type name(s) for the error message
                if isinstance(expected, tuple):
                    type_names = '/'.join(t.__name__ for t in expected)
                else:
                    type_names = expected.__name__
                issues.append(ValidationIssue(
                    rule_id='V023',
                    severity='error',
                    statement=index,
                    field=f'operation.params.{param_name}',
                    message=f'Parameter {param_name} must be {type_names}, got {type(param_value).__name__}',
                ))

    return issues


def _check_variable_length_paths(query: str, index: int) -> List[ValidationIssue]:
    """
    Check a Cypher query for unbounded or excessively deep variable-length paths (V030).

    Detects patterns like ``[*]``, ``[*..10]``, ``[*1..10]`` in Cypher relationship
    traversals. Paths without an upper bound (``[*]``, ``[*3..]``) are always rejected.
    Paths with an upper bound exceeding MAX_VARIABLE_PATH_LENGTH are rejected.

    Args:
        query: The Cypher query string from a CypherOp.
        index: Statement index for error reporting.

    Returns:
        List of V030 issues.

    @verified 0000000
    """
    issues: List[ValidationIssue] = []

    # Match [* ...] patterns: [*], [*3], [*1..5], [*..5], [*3..], etc.
    # The regex captures the full range spec after the *
    var_path_pattern = re.compile(
        r'\[\s*\*\s*'           # [*
        r'(\d+)?'               # optional lower bound
        r'(?:\s*\.\.\s*'        # optional .. separator
        r'(\d+)?)?'             # optional upper bound
        r'\s*\]'                # ]
    )

    for match in var_path_pattern.finditer(query):
        lower = match.group(1)
        upper = match.group(2)
        range_text = match.group(0)

        # No '..' at all and no number means [*] — fully unbounded
        has_range = '..' in range_text

        if not has_range and lower is None:
            # [*] — fully unbounded
            issues.append(ValidationIssue(
                rule_id='V030',
                severity='error',
                statement=index,
                field='operation.query',
                message=f'Unbounded variable-length path: {range_text.strip()}',
            ))
        elif not has_range and lower is not None:
            # [*3] — fixed-length path, check against limit
            depth = int(lower)
            if depth > MAX_VARIABLE_PATH_LENGTH:
                issues.append(ValidationIssue(
                    rule_id='V030',
                    severity='error',
                    statement=index,
                    field='operation.query',
                    message=f'Variable-length path depth {depth} exceeds maximum {MAX_VARIABLE_PATH_LENGTH}: {range_text.strip()}',
                ))
        elif has_range and upper is None:
            # [*1..] or [*..] — no upper bound
            issues.append(ValidationIssue(
                rule_id='V030',
                severity='error',
                statement=index,
                field='operation.query',
                message=f'Unbounded variable-length path (no upper limit): {range_text.strip()}',
            ))
        elif has_range and upper is not None:
            # [*1..5] or [*..5] — check upper bound
            depth = int(upper)
            if depth > MAX_VARIABLE_PATH_LENGTH:
                issues.append(ValidationIssue(
                    rule_id='V030',
                    severity='error',
                    statement=index,
                    field='operation.query',
                    message=f'Variable-length path depth {depth} exceeds maximum {MAX_VARIABLE_PATH_LENGTH}: {range_text.strip()}',
                ))

    return issues


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_operations(statements: List[Statement]) -> int:
    """
    Count total operations in a statement list.

    For conditional statements, takes the longer branch (then vs else) since
    that represents the worst-case execution cost. This ensures static
    boundedness: the executor can compute maximum query count before running.

    Args:
        statements: List of statements to count.

    Returns:
        Total operation count (int).

    @verified 0000000
    """
    total = 0
    for stmt in statements:
        op = stmt.operation
        if isinstance(op, ConditionalOp):
            then_count = _count_operations(op.then)
            else_count = _count_operations(op.else_) if op.else_ else 0
            total += max(then_count, else_count)
        else:
            total += 1
    return total


def _max_nesting_depth(statements: List[Statement], current_depth: int) -> int:
    """
    Compute maximum conditional nesting depth in a statement list.

    Walks the tree of ConditionalOp statements, tracking depth. Returns the
    deepest nesting level found (0 for flat programs, 1 for a single
    conditional, etc.).

    Args:
        statements: List of statements to analyze.
        current_depth: The nesting depth of the current context.

    Returns:
        Maximum nesting depth (int).

    @verified 0000000
    """
    max_depth = current_depth
    for stmt in statements:
        op = stmt.operation
        if isinstance(op, ConditionalOp):
            nested_depth = current_depth + 1
            then_depth = _max_nesting_depth(op.then, nested_depth)
            else_depth = _max_nesting_depth(op.else_, nested_depth) if op.else_ else nested_depth
            max_depth = max(max_depth, then_depth, else_depth)
    return max_depth


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_program(data: Any) -> ValidationResult:
    """
    Validate a GraphProgram AST through all validation layers.

    Runs four layers in order (cheapest first):
      1. Deserialization (V000) -- if this fails, subsequent layers are skipped
      2. Structural (V001-V005)
      3. Safety (V006-V007, V010-V016, V020-V023, V030)
      4. Semantic (future)

    Args:
        data: Raw JSON data (dict) representing a program.

    Returns:
        ValidationResult with ``valid`` flag, ``errors`` list, and ``warnings`` list.

    @verified 0000000
    """
    all_errors: List[ValidationIssue] = []
    all_warnings: List[ValidationIssue] = []

    # Layer 1: Deserialization
    program, l1_errors = _layer1_deserialize(data)
    all_errors.extend(l1_errors)

    if program is None:
        return ValidationResult(valid=False, errors=all_errors, warnings=all_warnings)

    # Layer 2: Structural
    l2_issues = _layer2_structural(program)
    all_errors.extend(l2_issues)

    # Layer 3: Safety
    l3_issues = _layer3_safety(program)
    for issue in l3_issues:
        if issue.severity == 'warning':
            all_warnings.append(issue)
        else:
            all_errors.append(issue)

    valid = len(all_errors) == 0
    return ValidationResult(valid=valid, errors=all_errors, warnings=all_warnings)
