# Issues

- [x] Need a mechanism for LLM to interact with it's commands output. E.g. running grep should continue chat with posting result of command. other commands: searching internet via command, asking for file contents. This ability supports resolving other issues.

- [x] It would be great to make LLM output (in the current LLM API wrapper) reliably multi-variable, e.g. have formatted object containing file source and other variables, like deciding on next step, or ending iterations in current chat. Perhaps a schema to validate and use ongoing chat to let it retry? This ability supports resolving other issues.

- [ ] runtime environment: running agent under conda clashes with agent's desire to use specific python version, and trying to resolve it installing a new version that never runs due to conda env hardcoded into bash environment. For other runtimes (npm, pnpm) there are similar problems.

- [x] source code discovery - we need to let agent decide which source files to add to the context for e.g. planning and debug stages (it only gets full file source in code editing stage). It needs to call grep to find files, it needs to search the internet.

- [ ] LLM still writes output instructions directed at human user with step-by-step like "open file, find line..., edit to include...", and occasional placeholders. Perhaps an iterative discovery skill can be used for LLM to trigger with command.

- [ ] Debugging agent operation is quite tedious - copious logs, a lot of noise. A log browser app would be very handy.
