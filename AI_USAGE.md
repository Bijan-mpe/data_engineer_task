# AI Coding Assistance Disclosure

This assignment requires transparency about AI tool usage during development.

## Instructions
Please complete the sections below honestly. Using AI tools is **acceptable and expected**. We want to understand **how** you used them.

## 1. AI Tools Used
List all AI coding assistants used.
- **Claude VS Code extension (`docs/CLAUDE_CHAT.md`)**: Used as the main code
  generator until Step 8. After that, I reached the usage limit and could not
  use it again until May 11th at 5 PM. The Claude chat log is not complete yet
  because of that limitation. After May 11th at 5 PM, I will request an export
  of the full chat and add it to the repository.
- **Codex (`docs/CODEX_CHAT.md`)**: Used as the code generator after I reached
  the Claude usage limit.
- **Codex (`docs/OVERVIEWER_CHAT.md`)**: Used as the code reviewer.

## 2. Components Assisted
Check which parts received AI assistance:

- [X] Data extraction logic (Excel parsing, MASTER sheet)
- [X] Data modeling design (ERD, table schemas, SCD Type 2)
- [X] ETL pipeline implementation
- [X] Data validation framework
- [X] API endpoint development (FastAPI)
- [X] Docker/Docker Compose configuration
- [X] SQL queries and migrations
- [X] Testing (unit/integration tests)
- [X] Documentation (README, comments)
- [X] Debugging specific issues
- [ ] Other: ___________

## 3. Detailed Description

I started working on the project on May 9 at 2 PM. I used AI across all
parts of the project, including implementation and code review. I reviewed the
AI outputs myself to make sure the generated code, tests, and documentation
matched the project requirements and quality expectations.

### Usage Approach

I used two different chats. One chat had write permission and was used to
generate files, code, and documentation. The other chat had read-only
permission and was used to review the code. To reduce mistakes statistically, I
used a repeated code-and-review cycle:

```text
Generate code -> Review and report -> Fix issues based on the report -> Review
the generated code again -> Fix remaining issues
```

I continued this cycle until the code reached the desired quality level. I also
reviewed both the generated code and the review reports myself, so I would not
waste time on issues I already knew about or suggestions that were not relevant.

For Claude, I started with the `/init` command, which generated a `CLAUDE.md`
file in the repository root. I then edited that file to improve the project
structure and define clean-code principles. I did not create custom skills
because I did not have enough time, but I think creating them would be worth it
for everyday development work.

For Codex, I copied the `CLAUDE.md` content into `AGENTS.md` to make sure Codex
had enough project context.


## 4. Chat History / Logs
Attach or link to chat history logs showing AI interactions.

**Format:** PDF, Markdown, screenshots, or text files
**Location:** `docs/CLAUDE_CHAT.md`, `docs/CODEX_CHAT.md`,
`docs/OVERVIEWER_CHAT.md`

**Note:** You may redact personal information but maintain enough context to show the AI interaction.


## 5. Self-Assessment
Reflect on your AI usage:

**What did AI do well?**
- It helped define SQLAlchemy ORM best practices for the current version.
- It implemented many tests that would have been time-consuming to write
  manually. Some tests were wrong at first, but even with review and fixes, the
  overall process was faster than writing everything myself.
- It helped find the root causes of complex bugs.
- It helped create and evaluate regular expressions.
- It implemented the pipeline in detail, although some bugs needed to be fixed.

**What did you need to correct or override?**
- I needed to correct the project structure.
- I needed to define the implementation steps and the main clean-code
  principles.
- It missed some constants, which I had to add.
- It initially missed consistent setup and usage of structlog across entrypoints
  and log call sites. I asked for a later pass to make logging consistently
  structured.
- It used a single `database_url` string. I preferred separate environment
  values and a computed field to generate the URL.
- Some tests were not good enough at first. I found several duplicated tests;
  for example, in the constants tests, a single constant was tested in multiple
  test functions. After refactoring, the number of tests was reduced from 46 to
  29. There were also some unnecessary tests, but I did not change all of them
  in order to save time.
- I added `duplicate` and `skipped` to the pipeline status constants and tests.
- It created an ERD and put SCD Type 2 fields inside the `company` table, but
  those fields needed to be in the snapshot table.
- It used UUIDs for `upload_audit`. UUIDs are a good choice in many systems,
  but for this assignment I preferred integer IDs because they are simpler to
  read in logs, reports, and API examples.
- It did not check the full industry weight sum correctly. The total must be
  1.0, but because floating-point arithmetic is not always exact, I suggested
  validating that the total weight is between 0.99 and 1.01.
- It put `reporting_currency`, `accounting_principles`, `business_year_end`,
  and `segmentation_criteria` inside `company` in the suggested ERD and
  `__init__.py` comments. I suggested moving them to the snapshot table.
- It forgot to add `version_number` to snapshot records.
- I changed the migration filename pattern.
- In Step 7, some validation rules were placed in Pydantic models and others
  were placed in the validator. This created two problems. First, future
  maintainers would need to look in two places for validation logic. Second,
  the behavior was inconsistent: Pydantic raises on the first error, while the
  validator collects all errors. If weight validation is in Pydantic and
  `risk_score` validation is in the validator, the pipeline behaves differently
  depending on which rule fails. I think all business validations should be
  implemented inside the validator.
- Logging initially was not based on the principle I defined, so I asked for a
  later pass to initialize structlog and use bound structured context.
- The endpoint requirements in `README.md` did not define API versioning. The
  AI initially followed the requirements literally, but to follow common API
  best practices, I used `/v1` routes in the implementation. I also added a
  `/health` endpoint.
- I asked AI to put every Codex chat message inside `docs/CODEX_CHAT.md`, but
  after Step 10 I realized it had inserted some new messages in the middle of
  the file. I asked it to fix the order, and it did.
- I also asked AI to create a `health_check` function for checking database
  connectivity. It is used by the `/health` endpoint.

**What did you implement entirely on your own?**
I just reviewed and manage and monitor the workflow.

**How did AI tools improve your development process?**
- It made me much faster, especially because I had to work on the assignment
  during my weekend.

**Were there any limitations or challenges with AI assistance?**
- Complex or unclear prompts can cause AI to create a messy repository.

## 6. Recommendations
Based on your experience, what advice would you give to others using AI tools for data engineering tasks?
- For this project, I preferred to avoid custom skills because I did not have
  enough time to create them, and I did not want to download ready-made skills
  from GitHub because I wanted to keep everything under control. However, using
  well-designed skills could improve code quality, especially for everyday
  development tasks.
- I used two AI tools at the same time: Claude to generate code, files, and
  documentation, and Codex to review the repository, suggest improvements, and
  find bugs.


Thank you for your transparency!
