# Project Agent Workflow

Use the project-scoped custom agents for non-trivial feature work and bug fixes.

1. Run `explore` to map the relevant code, data flow, conventions, and tests.
2. Give the exploration result to `plan`. Require a bounded plan and acceptance criteria.
3. Give the accepted plan to `code`. Keep one implementation owner to avoid edit conflicts.
4. Run `review` after implementation and validation. Give material findings back to `code`, then review the resulting diff again.

Do not run dependent stages in parallel. Parallelize only independent read-only exploration or review tasks. The primary agent owns user communication, resolves disagreements, and returns the final result.
