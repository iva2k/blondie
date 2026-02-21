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

## Todo

- [ ] 007 | P2 | Allow debugging the agent locally on dev machine |
- [ ] 008 | P3 | Vercel/Netlify CLI wrappers |
- [ ] 009 | P3 | Docker build + e2e tests |
- [ ] 010 | P3 | Deploy! |
- [ ] 011 | P4 | Multi-repo scanner + project.yaml |
- [ ] 012 | P4 | Agent should analyze tasks inter-dependency and update TASKS.md, new field "depends_on" | 002
- [ ] 013 | P4 | Tasks.py should pick blocking task first | 012
