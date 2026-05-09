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

**What did you need to correct or override?**
- I need to correct the project structure
- I need to define step of implementation and base principals of clean code.
- It missed some constants. I had to fix
- It missed setup structlog inside `core/logging.py`
- It used a single database_url string, Its weired, I used seperate env values and a computed field to generate it.
- Tests was not good, I found several duplication, for example in constants single constant was tested in several test function. after refactoring the number of test reduced to 29 from 46. There was also some no needed test but I didn't change them to save time.
- I added `duplicated` and `skipped` to the pipeline status constant and its tests.
- About 
**What did you implement entirely on your own?**

**How did AI tools improve your development process?**
- It made me so fast, specially when I had to work on the assignment in my week end.

**Were there any limitations or challenges with AI assistance?**
- complex and not clean prompt causes AI makes a messy repo.

## 6. Recommendations
Based on your experience, what advice would you give to others using AI tools for data engineering tasks?
- for this project I prefered to avoide SKILLs because I did not have much time to create them and I didn't also want to download ready skills from github to make sure everything is under control, but by using them the code quality will be improved.



Thank you for your transparency!
