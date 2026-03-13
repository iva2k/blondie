# Blondie Tasks

Status: id | priority | title | depends_on

## Done

### [Sprint1 2026-02]

- [x] 000 | P0 | Init repo structure |
- [x] 001 | P0 | Policy parser + gates |
- [x] 002 | P1 | TASKS.md parser + task claim |
- [x] 003 | P1 | Git CLI wrapper + branch automation |
- [x] 004 | P2 | LLM router + basic client |
- [x] 005 | P2 | Autonomous executor + shell wrapper |
- [x] 006 | P2 | Git branch based state + task locking |
- [x] 007 | P2 | Allow debugging the agent locally on dev machine |
- [x] 008 | P2 | Add repo files hierarchy to the context used in llm.plan_task()  |
- [x] 009 | P2 | Implement LLM code edits per the plan |
- [x] 010 | P3 | Failing test should trigger debugging loop and fix code (and possibly tests), retries should be for the test-debug-fix loop |
- [x] 011 | P3 | After failing test the agent leaves uncommited files and stumbles trying to restart the task |
- [x] 012 | P3 | Implement agent shell commands (with retry/debug loop). Flatten the errors up (or break outer edit loop) to the outer loop levels, as iterating recursively and editing files in inner loops can create layering problems when higher loop edits cancel lower loop edits. |
- [x] 020 | P0 | Implement journal - Option to log all chats to a trace dir/files (per task) |
- [x] 022 | P5 | in loop.py:BlondieAgent._get_files_context() use current .gitignore instead of hard-coded list |
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

### [Sprint2 2026-0304] Next-Gen Architecture (v2) - Recursive Skill Orchestration

- [x] 058 | P2 | [Phase 1] Update `Skill` class in `src/llm/skill.py` to parse `input_schema` and `output_schema` from frontmatter. |
- [x] 078 | P2 | [Phase 1] Implement `Skill.to_tool_definition()` in `src/llm/skill.py` to generate OpenAI/Anthropic tool schemas from `input_schema`. |
- [x] 069 | P2 | [Phase 1] Implement `output_schema` logic: Auto-inject "## Output Format" in `Skill.render_system_prompt` and add JSON schema validation to `ChatSession.send`. |
- [x] 070 | P2 | [Phase 1] Create v2 skills (`coding_plan_task`, `coding_debug_error`, `command_runner2`, `coding_get_file_edits`) copying v1. Remove redundant output instructions in favor of `output_schema`. |
- [x] 059 | P2 | [Phase 1] Update `ToolHandler` in `src/agent/tooled.py` to allow registering dynamic tools (callables) alongside hardcoded definitions. |
- [x] 073 | P2 | [Phase 1] Implement `write_file` primitive tool in `tooled.py` to allow Skills to perform side effects directly. |
- [x] 071 | P2 | [Quality] Update existing unit tests affected by Skill/Tool changes (e.g. `test_llm.py`, `test_tooled.py`). |
- [x] 060 | P2 | [Phase 2] Create `src/agent/loop2.py` skeleton (Orchestrator entry point). |
- [x] 061 | P2 | [Phase 2] Implement System Tools in `tooled.py`: Task Management (`get_next_task`, `claim_task`, `complete_task`). |
- [x] 062 | P2 | [Phase 2] Implement System Tools in `tooled.py`: Git Operations (`git_checkout`, `git_commit`, `git_push`, `git_merge`). |
- [x] 063 | P2 | [Phase 2] Implement System Tools in `tooled.py`: Execution & State (`run_tests`, `check_daily_limit`). |
- [x] 064 | P2 | [Phase 2] Create `skills/orchestrator.skill.md` defining the root agent persona and available tools (`plan_task2`, etc). |
- [x] 074 | P2 | [Phase 2] Create `coding_generate_code` skill to use `write_file` tool and return summary instead of content (Side-Effect Pattern). |
- [x] 065 | P2 | [Phase 2] Enhance `LLMRouter` in `src/agent/router.py` to handle recursive tool execution (Skill-as-Tool) and automatic Context Injection for sub-agents. |
- [x] 072 | P2 | [Quality] Add unit tests for new modules (`loop2.py`, recursive `router.py` logic). |
- [x] 067 | P2 | [Phase 3] Implement `summarize_and_restart` logic for long-running sub-agents (replaces 054, 057). |
- [x] 075 | P2 | [Phase 3] Implement Context Refresh: `ContextGatherer` needs a refresh method; Router calls it after tool execution to sync file lists. |
- [x] 076 | P2 | [Observability] Implement hierarchical logging in `Journal` (spans/indentation) to visualize recursive tool calls. |
- [x] 077 | P2 | [Observability] Update `LLMRouter` and `ToolHandler` to track execution depth and pass it to `Journal` methods for indentation. |
- [x] 068 | P2 | [Integration] Add CLI switch to run v2 loop (`loop2.py`). |
- [x] 079 | P2 | [Integration] Create a simple "Hello World" task in `TASKS.md` and verify v2 loop completes it (E2E test). |

### [Sprint3 2026-0310]

- [x] 088 | P1 | config params in project.yaml: exit_on_no_tasks "exit when no tasks left", exit_on_exception "exit in case of unhandled exception", otherwise agent should keep running forever. |
- [x] 092 | P1 | Create `docs/SKILLS.md` documentation - frontmatter fields, special logic in Blondie, explain context generator. |
- [x] 081 | P2 | [FEATURE] Skill convention: In loop2.py and `coding_orchestartor.skill.md` implement looping and exit decision logic based on LLM output (the idea was to have a tool call for summarize and restart - extent it for "loop" call). |
- [x] 089 | P1 | Ensure skill.md description frontmatter is used in tools context. Background: original skill.md files: "The top of skill.md file (the --- section) is parsed by the system before Agent even reads the full instructions. The description field should be injected into Agent's context window to help it decide if it should activate the skill." - meaning use description from the skill frontmatter for tools object. |
- [x] 090 | P1 | [FEATURE] In addition to daily cost limit, add max_total_cost_usd policy parameter and modify code to idle (or exit) instead of running. Perhaps rename `*check_daily_limit*` into `*check_run_limit*` so it can consolidate daily/total cost and token limits. |
- [x] 082 | P1 | Revisit context.py:_get_env_context(). Left for later. |
- [x] 086 | P2 | [DEV] consolidate scripts for `poe snapshot-dev` & `poe setup-dev` so _tmp/logs/ is handled in both snapshot and clear. Move `_tmp/logs/` to `_tmp/repo/_logs`, add .gitignore to project template |
- [x] 084 | P2 | [FEATURE] pull git main branch in pick_task tool before checking TASKS.md when there is no claimed task in local agent sandbox. Needed for swarm coordination using git. |
- [x] 091 | P3 | [Quality] After-sprint: Implement unit tests for low coverage modules used under loop2.py, increase modules low coverage to 80%. | 088, 092, 081, 089, 090, 082, 086, 084

### [Sprint4 2026-0311] Easy Start Wizard

- [x] 101 | P0 | [CLI] Refactor `src/agent/cli.py` to use `click.group`. Move existing logic to `run` subcommand (update ALL files calling agent.cli run and agent/cli). Add empty `init` subcommand. |
- [x] 102 | P0 | [Init] Implement `init_secrets` flow in `src/agent/cli.py init`. Prompt for keys, write to `/root/.blondie/secrets.env.yaml` (container path), and handle existing files. |
- [x] 103 | P0 | [Init] Implement `validate_secrets` flow. call `scripts/fetch_models.py` logic to test connectivity and generate `.agent/llm.yaml` in workspace. |
- [x] 104 | P0 | [Templates] Create `templates/basic` directory structure with default config files (`project.yaml`, `POLICY.yaml`, `TASKS.md`, `SPEC.md`, `ISSUES.md`, `llm_config.yaml`, `dev.yaml`, `.gitignore`). |
- [x] 105 | P1 | [Init] Implement `setup_workspace` flow. Detect if empty/git repo. Run `git init` if needed. Copy `templates/basic` files (overwrite protection, `.gitignore` appending). **Fix file permissions (chown) for Docker usage.** |
- [x] 106 | P1 | [Init] Implement `interview` flow. Prompt for Spec, Project ID, Git Identity, Model Provider, **Deployment Target**. Update config files. **Print final "Next Steps" with exact docker run command.** |
- [x] 107 | P2 | [Init] Implement `stack_detection` for existing projects. Detect Python/Node, pre-fill `project.yaml` commands, and ask for confirmation. |
- [x] 108 | P3 | [Dev] Enable debugging the wizard (`agent.cli init`) in local sandbox. |

### [Sprint5 2026-0312] Local Easy Start Wizard

- [x] 110 | P0 | [HTML Wizard] Rename `blondie.html` to `blondie.template.html`. Create `scripts/build_wizard.py` to recursively read `templates/` directory and inject file contents into `blondie.template.html` as a JSON object (replacing a placeholder), build `blondie.html` to be checked in. Add script to poe tasks. |
- [x] 111 | P0 | [HTML Wizard] Update `blondie.template.html` UI: Add Template Selection dropdown (populated from injected JSON keys) and Initial Tasks textarea. |
- [x] 112 | P0 | [HTML Wizard] Refactor `blondie.template.html` logic: Remove hardcoded file strings. Use injected template files as base. Apply user inputs (Secrets, Project ID, Deploy Target, Tasks) on top of the selected template. |
- [x] 113 | P1 | [CLI Wizard] Update `src/agent/wizard.py` to list available subdirectories in `templates/` and prompt user to select one (defaulting to 'basic' or auto-detected stack). |
- [x] 114 | P1 | [CLI Wizard] Update `src/agent/wizard.py` interview to prompt for "Initial Tasks" and append them to `TASKS.md`. |
- [x] 115 | P1 | [Templates] Create `templates/python` and `templates/node` directories with specific `project.yaml` and `dev.yaml` configurations to support template selection in wizards. |
- [x] 116 | P1 | [HTML Wizard] Add "Use SSH for Git?" checkbox to UI and update the generated `docker run` command logic to include `-v ~/.ssh:/root/.ssh:ro`. |
- [x] 117 | P2 | [Build] Create E2E test to verify `scripts/build_wizard.py` correctly generates `blondie.html` and that the generated file passes `tests/test_init_html.py`. |
- [x] 118 | P2 | [Wizards] Add Groq API Key prompt to `setup_secrets` (CLI) and `blondie.template.html` (HTML) to match supported providers in `DEPLOY.md`. Make the list of providers dynamic based on `llm_config.yaml` from the template |

- [x] 119 | P2 | [Wizards] Add unit and e2e tests for 80% coverage of 110, 111, 112, 113, 114, 115, 116, 117, 118. |

## Todo

### [Sprint6 2026-0312] Wizard and Actual Deployment

- [x] 120 | P1 | [HTML Wizard] "Use SSH for Git (mounts ~/.ssh)" should be grouped with GIT token field (the group should precede API keys group) - if SSH is selected, we should have a file selector / dropbox for cert file, if not selected, token field entry. The file should be copied into the zip folder under `./home/$USER/.ssh/id_rsa`. |
- [x] 121 | P1 | [CLI Wizard] Similar to HTML, add "Use SSH for Git (mounts ~/.ssh)" which should choose either a file name to copy, or GIT token prompt (the group should precede API keys group) - if SSH is selected, the file should be copied into the zip folder under `./home/$USER/.ssh/id_rsa`. |
- [x] 122 | P1 | [Agent Startup] The agent should detect running the first time (marked "unconfigured"). We need a mechanism to receive the configuration zip file from the wizard. Upon receipt of the file, it should install the content, including the cert file for GIT, and configure GIT to use the cert file, and mark itself as "configured", so upon consequent starts it will go into runnning state. |
- [x] 123 | P1 | [Upload] zip file upload from local system to agent system's config upload server. |
- [ ] 124 | P1 | [Upload] Add documentation about agent configuration upload server and local system upload client in DEPLOY.md and DEPLOY-SPEC.md. |

### [GOAL]

- [ ] 015 | P4 | **DEPLOY!** Start self-editing | 082

### Future

- [ ] 096 | P5 | [FEATURE] Use and keep updating SPEC.md |
- [ ] 097 | P5 | [FEATURE] Use secrets file from `~/.blondie/secrets.env.yaml` if `.agent/secrets.env.yaml` does not exist. |
- [ ] 018 | P3 | [FEATURE] Tasks.py should pick blocking task first. Priority of blocking task should elevate to blocked task priority when considering what to pick.  |
- [ ] 080 | P3 | skill.md format is quite elaborate. Implement skill.md checker script and poe task. Ensure {context} is present in system prompt if context frontmatter is listed, but "## CONTEXT" header is not present, as it is inserted programmatically. Ensure context items are listed if there are references, e.g. `[PROGRESS]`, in the system prompt. Ensure `user-content` has fields mentioned by reference. |
- [ ] 092 | P5 | [FEATURE] Use tool `summarize_and_restart` in coding_orchestrator - when struggling on a single task for multiple sessions. |
- [ ] 093 | P5 | [FEATURE] Connect Claude models (add API key) |
- [ ] 094 | P5 | [FEATURE] Connect Gemini models (add API key) |
- [ ] 083 | P5 | [FEATURE] Generalize loop2.py - allow any skill orchestrator to be selected by argument, remove any hard-coded flow specific to `coding_orchestartor.skill.md`. Needed for Different agent personalities from same codebase. | 081
- [ ] 013 | P5 | [FEATURE] Vercel/Netlify CLI wrappers |
- [ ] 014 | P5 | [FEATURE] Docker build + e2e tests |
- [ ] 016 | P5 | [FEATURE] Multi-repo scanner + project.yaml | 038
- [ ] 038 | P5 | [for 016] Allow multirepo - limit agent to a project subfolder inside a bigger repo |
- [ ] 017 | P5 | [FEATURE] Agent should analyze tasks inter-dependency and update TASKS.md, new field "depends_on" |
- [ ] 021 | P5 | [FEATURE] Add "details" field to TASKS.md, so title could be short, similar to most bug trackers. Prompts bigger rethink - how TASKS.md is best structured? BugTrackers usually have discussions pre- and post- implementation.  |
- [ ] 041 | P5 | [FEATURE] Agent should communicate with external world: email, slack, twitter. Commands: reboot, terminate, pause/resume. Events: task queue stuck (all tasks blocked, can't finish blockers), Deploy triggered. Carefull as swarm will flood the channels. | 088
- [ ] 082 | P5 | [CLEANUP] Remove loop.py and it's hard-coded skills: [plan_task, get_file_edits, generate_code, debug_error], wrappers for these skills in router.py, related unit tests. |
- [ ] 085 | P5 | [CLEANUP] When loop.py is removed, cleanup command_runner vs command_runner2 skills. | 082
- [ ] 087 | P5 | [FEATURE] Done tasks should be moved from TASKS.md to docs/CHANGELOG.md. Need a toolified skill for that. Consider how removing task from TASKS.md can affect agents swarm (probably not). |
- [ ] 095 | P5 | [FEATURE] Centralized coordination and reporting, e.g. total cost accrued. Use database? Remove local usage.yaml. (Needed for agents swarm) |
- [ ] 098 | P5 | [FEATURE] Add "follow-up:" questions to skills frontmatter. LLM may improve results after initial answer if follow-ups are asked. |
- [ ] 099 | P5 | [FEATURE] Add Docs update skill to orchestrator workflow |
- [ ] 100 | P5 | [FEATURE] Add self-learning (save acquired knowledge to <TBD>.md ) to orchestrator workflow |
- [ ] 109 | P1 | Move some config settings from project.yaml to POLICY.yaml |
