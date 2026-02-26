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
- [x] 026 | P0 | Timeout for shell commands and prompt instructions to use non-interactive options. |
- [x] 029 | P1 | In journal, add all shell commands, their return code and stdout/sterr |
- [x] 030 | P1 | In journal, add system prompt, endpoint URL, and model name to LLM entries |
- [x] 034 | P1 | subprocess.run() hangs on Windows despite timeout=120 on e.g. `poetry cache clear --all pypi` which shows user prompt |
- [x] 031 | P2 | Put Journal files into log/\<project_id>/task\<id>/ subfolders |
- [x] 033 | P1 | In journal, log complete untruncated messages. When passing messages to console, truncate these long ones. |
- [x] 032 | P1 | Add a fixed files list (e.g. .agent/POLICY.yaml) to never list to LLM context and never allow editing (use gitignore.py mechanism) |
- [x] 037 | P1 | Inform LLM of python environment (conda/venv/poetry) via dev.yaml config and context injection. |
- [x] 025 | P3 | Use router.py:LLMRouter.check_daily_limit() |
- [x] 039 | P3 | refactor LLM router code - use common worker method, each existing method should call the worker with system prompt, user prompt, etc. |
- [x] 042 | P3 | Track task cost, When task is done, log to journal and console task cost |
- [x] 043 | P3 | When exiting agent (even by keyboard interrupt), log to journal and console total daily cost |
- [x] 044 | P1 | Remove gates copy from top level of Policy (conserve context) |
- [x] 045 | P1 | Implement structured output validation in LLMRouter (JSON schema) with auto-retry on validation failure. |
- [x] 046 | P1 | Implement ChatSession in LLMRouter to support multi-turn conversations with tool execution (REPL) for skills. |
- [x] 047 | P1 | Add `tools` definition to Skill class and implement basic shell/file tools for the interactive session. |

## Todo

- [ ] 048 | P2 | Update Planning skill to use interactive tool loop for repo exploration (grep, find, read). |

- [ ] 027 | P1 | Connect stderr/stdout/stdin of shell commands interactively to LLM, so it could respond to prompts |
- [ ] 028 | P2 | In shell command retry/debug loop - Flatten the errors up to the outer loop levels, as iterating recursively and editing files in inner loops can create layering problems when higher loop edits cancel lower loop edits or the higher plan is derailed. | 027

- [ ] 035 | P2 | compose summary and LLM notes of previous chat in debug-fix LLM loop, so LLM could understand that it beats on the same problem and could try different approaches | 037
- [ ] 040 | P3 | Agent should have its user/email set for git commits |

- [ ] 015 | P4 | **DEPLOY!** Start self-editing | 025, 032, 037, 028, 035, 025, 039

- [ ] 013 | P3 | Vercel/Netlify CLI wrappers |
- [ ] 014 | P3 | Docker build + e2e tests |
- [ ] 016 | P4 | Multi-repo scanner + project.yaml |
- [ ] 017 | P4 | Agent should analyze tasks inter-dependency and update TASKS.md, new field "depends_on" |
- [ ] 018 | P4 | Tasks.py should pick blocking task first |
- [ ] 019 | P4 | Easy start - detect and run first start script to collect all info from user and create starting repo from template files |
- [ ] 021 | P5 | Add "details" field to TASKS.md, so title could be short, similar to most bug trackers |
- [ ] 036 | P5 | Use grep to allow LLM finding all relevant source files |
- [ ] 038 | P5 | Allow multirepo - limit agent to a project subfolder inside a bigger repo |
- [ ] 041 | P5 | Agent should communicate with external world: email, slack, twitter. Events: task queue stuck (all tasks blocked, can't finish blockers), Deploy triggered. Carefull as swarm will flood the channels. |
