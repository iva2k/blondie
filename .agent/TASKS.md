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
- [x] 026 | P0 | Timeout for shell commands and prompt instructions to use non-interactive options. |

## Todo

- [ ] 020 | P0 | Implement journal - Option to log all chats to a trace dir/files (per task) |
- [ ] 027 | P1 | Connect stderr/stdout/stdin of shell commands interactively to LLM, so it could respond to requests |
- [ ] 012 | P3 | Implement agent shell commands (with retry/debug loop). Flatten the errors up (or break outer edit loop) to the outer loop levels, as iterating recursively and editing files in inner loops can create layering problems when higher loop edits cancel lower loop edits. | 026, 027
- [ ] 013 | P3 | Vercel/Netlify CLI wrappers |
- [ ] 014 | P3 | Docker build + e2e tests |
- [ ] 015 | P3 | Deploy! Start self-editing | 025, 026
- [ ] 016 | P4 | Multi-repo scanner + project.yaml |
- [ ] 017 | P4 | Agent should analyze tasks inter-dependency and update TASKS.md, new field "depends_on" | 002
- [ ] 018 | P4 | Tasks.py should pick blocking task first | 012
- [ ] 019 | P4 | Easy start - detect and run first start script to collect all info from user and create starting repo from template files |
- [ ] 021 | P5 | Add "details" field to TASKS.md, so title could be short, similar to most bug trackers |
- [ ] 022 | P5 | in loop.py:BlondieAgent._get_file_tree() use current .gitignore instead of hard-coded list |
- [ ] 023 | P5 | in loop.py:BlondieAgent._apply_llm_edits() implement dict for continuous action verbs, i.e. fix "Create-ing" |
- [ ] 024 | P5 | in router.py:LLMRouter._init_clients() raise error for not configured API endpoint |
- [ ] 025 | P5 | Use router.py:LLMRouter.check_daily_limit() |
