# AGENTS.md: house rules

SPEC.md is the only source of requirements. Where it is silent, stop and ask. Never invent a rule, amount or column.

1. No em dashes anywhere: code, comments, docs, commit messages, tickets.
2. Money is integer cents. `BIGINT` in storage, `int` in Python. No floats in the domain package, and no float or numeric column types for money.
3. The domain package (`api/fernway/domain`) has no I/O imports: no FastAPI, SQLAlchemy, file, network or clock access.
4. One ticket per PR, one branch per ticket (`fm-XX`). Diff stays under about 400 lines, excluding fixtures and generated code.
5. Every ticket ends with the evidence block from its ticket file and a green `make test`.
6. Every constant traces to SPEC.md, `config/rules.yaml` or `docs/DECISIONS.md`.
7. Layering: routes, services, domain (pure), repositories. Enforced by import-linter.
8. Undecided or unknown means blocked (fail-closed). Never default a null rule.
9. The AI assistant is read-only and never touches money.
10. No subagents or parallel workers without the owner's explicit OK.
11. Stop and ask when: two spec sections conflict, a needed business value is missing, a ticket exceeds 5 acceptance lines or about 400 lines, or an approach fails twice.
