# Unified Query Language — Block Editor Round-Trip

## Status: Superseded by ADR-500

The design questions in this document (block editor round-trip, smart blocks in
the IR, text syntax extensions, execution engine unification) are now answered
by the formal GraphProgram language specification:

- **Language spec:** `docs/language/specification.md`
- **Validation rules:** `docs/language/validation.md`
- **Security model:** `docs/language/security.md`
- **Lifecycle:** `docs/language/lifecycle.md`
- **Executable spec:** `api/app/models/program.py`, `api/app/services/program_validator.py`, `tests/unit/test_program_validation.py` (109 tests)
- **ADR:** `docs/architecture/query-search/ADR-500-graph-program-dsl-and-ast-architecture.md`

### What ADR-500 resolved

| Original question | Resolution |
|---|---|
| Smart blocks in the IR? | `ApiOp` — first-class operation type with endpoint allowlist |
| Text syntax extensions? | Text DSL defined in spec Section 6 (`@block` annotations, `@api` directives) |
| Block decompilation? | `BlockAnnotation` on each Statement enables AST→blocks round-trip |
| Unified executor? | Single `GraphProgram` executor replaces 3 separate execution paths |
| Set algebra beyond +/-? | 5 operators: `+` `-` `&` `?` `!` |

### Remaining implementation (tracked in ADR-500 phases)

| Phase | What |
|-------|------|
| Phase 1 (done) | Language spec, validation, executable tests |
| Phase 2 | API endpoints (POST /programs, validate, GET), client integration |
| Phase 3 | ConditionalOp, $param substitution |
| Phase 4 | Text DSL parser, AST↔Blocks round-trip |
