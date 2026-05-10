# AI Coding Assistance Disclosure

This assignment requires transparency about AI tool usage during development.

## Instructions
Please complete the sections below honestly. Using AI tools is **acceptable and expected**. We want to understand **how** you used them.


## 1. AI Tools Used
List all AI coding assistants used.


## 2. Components Assisted
Check which parts received AI assistance:

- [ ] Data extraction logic (Excel parsing, MASTER sheet)
- [ ] Data modeling design (ERD, table schemas, SCD Type 2)
- [ ] ETL pipeline implementation
- [ ] Data validation framework
- [ ] API endpoint development (FastAPI)
- [ ] Docker/Docker Compose configuration
- [ ] SQL queries and migrations
- [ ] Testing (unit/integration tests)
- [ ] Documentation (README, comments)
- [ ] Debugging specific issues
- [ ] Other: ___________


## 3. Detailed Description
For each major component, describe how AI assisted.


## 4. Chat History / Logs
Attach or link to chat history logs showing AI interactions.

**Format:** PDF, Markdown, screenshots, or text files
**Location:** [Provide links or attach files here]

**Note:** You may redact personal information but maintain enough context to show the AI interaction.


## 5. Self-Assessment
Reflect on your AI usage:

**What did AI do well?**
- defining sqlalchemy orm bestpractices of the last version.
- Implemented lots of tests that is so time consuming when it is going to be writen by human.(It made wrong tests, but, overal speed by fixing the wrong test its also faster than me at the end than)
- It found complex bugs main reasons.
- Creating regex evaluation.
- Implement Pipeline with details, but with some bugs
**What did you need to correct or override?**
- I need to correct the project structure
- I need to define step of implementation and base principals of clean code.
- It missed some constants. I had to fix
- It missed setup structlog inside `core/logging.py`
- It used a single database_url string, Its weired, I used seperate env values and a computed field to generate it.
- Tests was not good, I found several duplication, for example in constants single constant was tested in several test function. after refactoring the number of test reduced to 29 from 46. There was also some no needed test but I didn't change them to save time.
- I added `duplicated` and `skipped` to the pipeline status constant and its tests.
- It created ERD and put SDC type2 fields inside company table but it must be inside snapshot.
- It used UUID for upload_audit, that is good but to make it simple to read logs and etc, I suggest to change to int.
- It didn't checked whole industry weights, it must be 1 and because it is float and is not very acurate in some cases like 0.333 + 0.333 + 0.334 = 1.0000000000000002, i sugest validate if th whole weight is between .99 and 1.01.
- It puted reporting_currency, accounting_principles, business_year_end, segmentation_criteria fields inside company in sugested erd, inside __init__.py coments. I suggest to move them to the snapshot table.
- it forgot to add version_number to snapshot records. 
- I changed the pattern of migrations file names. 
- In step7, validation implementation, some validations are places in pydantic models and another some in validator, it make two problem, one is that there are tow place to look for future development, second is inconsistent behavior. Pydantic raises on first error then validator collects all errors. If weight sum is in Pydantic and risk_score is in the validator, the pipeline behaves differently depending on which rule fails. 
I think all the validations must be implemented inside validator. 
- Logging is not based on the principal I defined, I will fix it at the end if I have time.
- 
**What did you implement entirely on your own?**

**How did AI tools improve your development process?**
- It made me so fast, specially when I had to work on the assignment in my week end.

**Were there any limitations or challenges with AI assistance?**
- complex and not clean prompt causes AI makes a messy repo.

## 6. Recommendations
Based on your experience, what advice would you give to others using AI tools for data engineering tasks?
- for this project I prefered to avoide SKILLs because I did not have much time to create them and I didn't also want to download ready skills from github to make sure everything is under control, but by using them the code quality will be improved.
- I use two AI at same time Claude that generates code, files and writes to repo, and Codex tha just reviews the repo and suggests improvement or finds bugs. 


Thank you for your transparency!

<!-- these section is not about ai agents -->
# Implementation assumption
- at each time one instance of the pipeline is runnign. I handled some concurrent runing issues but I have not deeply check if it is safe to run several instance of a pipeline at same time with shared data/ volume.
- I assume that idempotency can be based on file content, but there can be other case that data analyst want to test same content as a test case, in the case hash of filename+filecontent is better.
- another thing that must be considered is that our current implementation uses syncsqlalchemy with fastapi, that is totally acceptable now, but for a production async api, we should either make the route handlers sync def, allowing fastapi to run them in a threadpool, or migrate the db layer to SQLAlchemy async engine with AsyncSession.
- 
# TASKs

- [ ] Expand the Step 8 run summary into a full data-quality report. Current
  `PipelineBatchReport.validation_error_count` only counts validator errors
  attached to per-file reports; extraction failures, load failures, audit-write
  failures, warning counts, validity rates, and rule-level completeness metrics
  should be represented in a later reporting step.
- [ ] Convert all logs to JSON structured logs using `structlog`. At the
  beginning of each process, bind shared context with `structlog`'s `bind`
  pattern so every following log line carries the same process/file/run
  context until the process finishes. This will make log querying, checking,
  and monitoring-system integration much easier.
- [ ] 
