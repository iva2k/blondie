# Blondie Tasks

Status: id | priority | title | depends_on

## Done

- [x] 000 | P0 | Init repo structure |
- [x] 001 | P0 | Policy parser + gates |
- [x] 002 | P1 | TASKS.md parser + task claim |
- [x] 003 | P1 | Git CLI wrapper + branch automation |
- [x] 004 | P2 | LLM router + basic client |

## Todo

- [ ] 005 | P2 | Autonomous executor + shell wrapper |
- [ ] 006 | P2 | Git branch based state + task locking | 003
- [ ] 007 | P3 | Multi-repo scanner + project.yaml |
- [ ] 008 | P3 | Vercel/Netlify CLI wrappers |
- [ ] 009 | P3 | Docker build + e2e tests |
- [ ] 010 | P3 | Deploy! |
- [ ] 011 | P3 | Allow debugging the agent locally on dev machine |
- [ ] 012 | P3 | Agent should analyze tasks inter-dependency and update TASKS.md, new field "depends_on" | 002
- [ ] 013 | P3 | Tasks.py should pick blocking task first | 012
