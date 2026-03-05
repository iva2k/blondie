# Blondie Tasks

Status: id | priority | title | depends_on

## Done

- [x] 000 | P0 | Init repo structure |
- [x] 001 | P0 | Policy parser + gates |
- [x] 002 | P1 | TASKS.md parser + task claim |
- [x] 003 | P1 | Git CLI wrapper + branch automation |
- [x] 004 | P2 | LLM router + basic client |
- [x] 005 | P2 | Autonomous executor + shell wrapper |
- [x] 006 | P2 | Git branch based state + task locking | 003
- [x] 007 | P2 | Allow debugging the agent locally on dev machine |
- [x] 008 | P2 | Add repo files hierarchy to the context used in llm.plan_task()  |
- [x] 009 | P2 | Implement LLM code edits per the plan |
- [x] 010 | P3 | Failing test should trigger debugging loop and fix code (and possibly tests), retries should be for the test-debug-fix loop |
- [x] 011 | P3 | After failing test the agent leaves uncommited files and stumbles trying to restart the task |
- [x] 012 | P3 | Implement agent shell commands (with retry/debug loop). Flatten the errors up (or break outer edit loop) to the outer loop levels, as iterating recursively and editing files in inner loops can create layering problems when higher loop edits cancel lower loop edits. |
- [x] 020 | P0 | Implement journal - Option to log all chats to a trace dir/files (per task) |
- [x] 022 | P5 | in loop.py:BlondieAgent._get_file_tree() use current .gitignore instead of hard-coded list |
- [x] 023 | P5 | in loop.py:BlondieAgent._apply_llm_edits() implement dict for continuous action verbs, i.e. fix "Create-ing" |
- [x] 024 | P5 | in router.py:LLMRouter._init_clients() raise error for not configured API endpoint |
- [x] 025 | P3 | Use router.py:LLMRouter.check_daily_limit() |
- [x] 026 | P0 | Timeout for shell commands and prompt instructions to use non-interactive options. |
- [x] 027 | P3 | Connect stderr/stdout/stdin of shell commands in tools and planned actions interactively to LLM, so LLM could respond to shell command prompts. Use new SKILL `command_runner.skill.md`, and give it proper context - current command, task and action instruction. |
- [x] 029 | P1 | In journal, add all shell commands, their return code and stdout/sterr |
- [x] 030 | P1 | In journal, add system prompt, endpoint URL, and model name to LLM entries |
- [x] 031 | P2 | Put Journal files into log/\<project_id>/task\<id>/ subfolders |
- [x] 032 | P1 | Add a fixed files list (e.g. .agent/POLICY.yaml) to never list to LLM context and never allow editing (use gitignore.py mechanism) |
- [x] 033 | P1 | In journal, log complete untruncated messages. When passing messages to console, truncate these long ones. |
- [x] 034 | P1 | subprocess.run() hangs on Windows despite timeout=120 on e.g. `poetry cache clear --all pypi` which shows user prompt |
- [x] 035 | P2 | Compose summary (progress.txt) of actions, so LLM could understand that it beats on the same problem and could try different approaches |
- [x] 036 | P2 | In SKILL prompts / INSTRUCTIONS Encourage use of grep to allow LLM finding all relevant source files |
- [x] 037 | P1 | Inform LLM of python environment (conda/venv/poetry) via dev.yaml config and context injection. |
- [x] 039 | P3 | refactor LLM router code - use common worker method, each existing method should call the worker with system prompt, user prompt, etc. |
- [x] 040 | P1 | Agent uses its user/email (set in project.yaml) for git commits |
- [x] 042 | P3 | Track task cost, When task is done, log to journal and console task cost |
- [x] 043 | P3 | When exiting agent (even by keyboard interrupt), log to journal and console total daily cost |
- [x] 044 | P1 | Remove gates copy from top level of Policy (conserve context) |
- [x] 045 | P1 | Implement structured output validation in LLMRouter (JSON schema) with auto-retry on validation failure. |
- [x] 046 | P1 | Implement ChatSession in LLMRouter to support multi-turn conversations with tool execution (REPL) for skills. |
- [x] 047 | P1 | Add `tools` definition to Skill class and implement basic shell/file tools for the interactive session. |
- [x] 048 | P2 | Update Planning skill to use interactive tool loop for repo exploration (grep, find, read). |
- [x] 049 | P5 | add number of tool requests in journal.log_chat
- [x] 050 | P2 | Measure time of shell commands (both tools and yaml), show in journal
- [x] 051 | P3 | Script in scripts/ to query available LLM models from API, save to file .agent/llm.yaml. Then use the file in client.py to select models.
- [x] 052 | P3 | Script in scripts/ to query LLM models cost (scrape vendor webpage if no API), save to file .agent/llm.yaml. Use the file in client.py and use costs in router.py to track costs.
- [x] 053 | P1 | In SKILL plan_task prompt add after "Initialize project" "... and install packages" (so that section is meaningfull for more tasks) |
- [x] 055 | P1 | Put journal files under `_tmp/log/task-ID/` dir. Make a script (in scripts/) and poe task to move/copy (argument choice) whole `_tmp/` to a dated `_tmp.YYYY-MMDD2-hhmm/` for saving complete trace/snapshot of interesting debug runs |

## Todo


- [ ] 015 | P4 | **DEPLOY!** Start self-editing | 025, 032, 037, 028, 035, 025, 039

- [ ] 058 | P5 | Add toolify to skills - use frontmatter data to compose tool definition for the skill, add to tooled.py roster of tools. (with that, skills could chain each other by pure declaration of the available tools in frontmatter.tools ) |
- [ ] 028 | P5 | In shell command retry/debug loop - concern is the nested loops that may negate the higher-level loop plan and wipe the lower level loop fixes out. Flatten the errors up to the outer loop levels, as iterating recursively and editing files in inner loops can create layering problems when higher loop edits cancel lower loop edits or the higher plan is derailed. This is philosophical. | 056, 057
- [ ] 056 | P5 | Philosophical: [solve 028] Should we micro-manage the agent (rigidly chain the steps), or let it choose what to do and when? Decide its workflow, pick next skill. Skills could have required inputs, and agent can call skills as tools. **BIG IDEA**: wrap skills as tools and add to a collection of tools that includes (current) hard-coded ones. The agent will be able to orchestrate itself. Further, the agent will be able to create its own tool-skills.
- [ ] 057 | [for 028] Fight context rot and endless loops: Use 1. continuation (nested tool calls) and 2. "restart itself" - with summarized knowledge call itself as a tool, but for breaking the loop it can replace self chat history in the tool call chain. | 054
- [ ] 054 | P5 | Compose summary notes of LLM thinking findings in debug-fix LLM loop, so LLM could understand later that it beats on the same problem and could try different approaches |

- [ ] 013 | P5 | [FEATURE] Vercel/Netlify CLI wrappers |
- [ ] 014 | P5 | [FEATURE] Docker build + e2e tests |
- [ ] 016 | P5 | [FEATURE] Multi-repo scanner + project.yaml | 038
- [ ] 038 | P5 | [for 016] Allow multirepo - limit agent to a project subfolder inside a bigger repo |
- [ ] 017 | P5 | [FEATURE] Agent should analyze tasks inter-dependency and update TASKS.md, new field "depends_on" |
- [ ] 018 | P5 | [FEATURE] Tasks.py should pick blocking task first |
- [ ] 019 | P5 | [FEATURE] Easy start - detect and run first start script to collect all info from user and create starting repo from template files |
- [ ] 021 | P5 | [FEATURE] Add "details" field to TASKS.md, so title could be short, similar to most bug trackers. Prompts bigger rethink - how TASKS.md is best structured? BugTrackers usually have discussions pre- and post- implementation.  |
- [ ] 041 | P5 | [FEATURE] Agent should communicate with external world: email, slack, twitter. Events: task queue stuck (all tasks blocked, can't finish blockers), Deploy triggered. Carefull as swarm will flood the channels. |
