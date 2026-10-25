# GLOBAL AI CODING & PERMISSION RULES (BILLINGSYSTEM / BILLMASTER)

This document defines mandatory, non-negotiable rules for any AI agent, coding assistant, or developer working on the BillingSystem/BillMaster codebase.

---

## 1. PERMISSION & SECURITY RESTRICTIONS (STRICT)

1. **Confidentiality & Secret Protection**:
   - **NEVER** view, read, print, log, or leak sensitive confidential files (e.g., `.env`, `.env.*`, production secrets, API keys, credentials).
   - If a configuration or environment variable is needed, reference its key name from `.env.example` only.

2. **No Direct Database Manipulation**:
   - **NEVER** run direct SQL mutations, manual updates, deletes, or drops against hosted, staging, or production databases (e.g., Neon, Railway).
   - Only execute local, isolated test fixtures or user-authorized Alembic migrations.

3. **Core Logic Preservation**:
   - **NEVER** alter financial calculations, ledger balance logic, tax rules, stock/inventory logic, or core business workflows without prior explanation, discussion, and explicit user consent.
   - Always trace existing implementations and reuse established business behaviors.

4. **Git Branch & Deployment Boundary**:
   - **NEVER** commit, push, create PRs, merge, or deploy without explicit user authorization.
   - Strictly follow the repository branch workflow:
     ```
                 main
                  |
                 UAT
                /   \
          backend   frontend
     ```
   - All backend work stays on `backend`; frontend work stays on `frontend`; integration is tested on `UAT`; releases are promoted from `UAT` to `main`.

---

## 2. CODE QUALITY & EFFICIENCY RULES

1. **Efficiency (Time & Space Complexity)**:
   - Always write computationally efficient code with low time complexity and minimal database footprint.
   - Avoid redundant database queries, duplicate indexing, unindexed joins, or unnecessary memory allocations.

2. **Concise, Clean & Impactful Code**:
   - Prefer compact, direct, and readable implementations over sprawling helper functions and bloated multi-layered abstractions.
   - Every line of code must serve a clear purpose; do not write 50 lines where 10 impactful, readable lines do the same job better.

3. **Database Integrity & Check Constraints**:
   - Strictly adhere to database check constraints and domain rules:
     - Zero balance rule: In `account_ledgers`, when `balance = 0`, `balance_type` MUST be `NULL` (`None`).
     - GSTIN & PAN alignment: If GSTIN is present, `state_code` must match the first 2 characters, and `pan_card` must match characters 3–12.
     - Single atomic transaction: Multi-table operations (e.g., legacy Customer/Party + Account + Role + Ledger + Mapping) must happen in the same transaction. If any part fails, everything rolls back.

4. **Regression Prevention**:
   - Every change must preserve backward compatibility with existing legacy endpoints until deliberate cutover.
   - Test suites must always pass with 100% success before finishing any task.

