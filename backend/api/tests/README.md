# Billing backend test structure

This test suite is organised by feature and test type.

## Shared folders

- `fixtures/`: pytest fixtures only
- `factories/`: database object builders
- `data/`: API payload builders and static test data
- `helpers/`: reusable assertions and utility functions

## Feature folders

Each backend feature contains:

- `unit/`: schema and service tests without the full HTTP flow
- `integration/`: route-to-database API tests using an isolated test database

## Rules

1. Production code stays outside `api/tests`.
2. Tests must never use the development or production database.
3. `conftest.py` stays small and only registers/imports fixtures.
4. Feature-specific setup belongs in the matching fixture/factory/data module.
5. Do not duplicate payloads or assertions across test files.
6. Add repository and validator unit tests later when those production layers are introduced.

## Planned implementation order

1. Isolated PostgreSQL test database
2. Database and TestClient fixtures
3. Party and Customer tests
4. Remaining feature tests
5. Coverage reporting and CI
