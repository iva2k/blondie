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

## Todo

- [ ] 010 | P3 | Implement agent shell commands, such as adding & installing packages |
- [ ] 011 | P3 | Vercel/Netlify CLI wrappers |
- [ ] 012 | P3 | Docker build + e2e tests |
- [ ] 013 | P3 | Deploy! Start self-editing |
- [ ] 014 | P4 | Multi-repo scanner + project.yaml |
- [ ] 015 | P4 | Agent should analyze tasks inter-dependency and update TASKS.md, new field "depends_on" | 002
- [ ] 016 | P4 | Tasks.py should pick blocking task first | 012
- [ ] 017 | P4 | Easy start - detect and run first start script to collect all info from user and create starting repo from template files |
- [ ] 018 | P5 | Option to log all chats to a trace dir/files (per task) |
- [ ] 019 | P5 | Add "details" field to TASKS.md, so title could be short, similar to most bug trackers |
- [ ] 020 | P5 | in loop.py:BlondieAgent._get_file_tree() use current .gitignore instead of hard-coded list |
- [ ] 021 | P5 | in loop.py:BlondieAgent._apply_llm_edits() implement dict for continuous action verbs, i.e. fix "Create-ing" |
- [ ] 022 | P5 | in router.py:LLMRouter._init_clients() raise error for not configured API endpoint |
