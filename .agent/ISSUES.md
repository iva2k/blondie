# Issues

- [x] Need a mechanism for LLM to interact with it's commands output. E.g. running grep should continue chat with posting result of command. other commands: searching internet via command, asking for file contents. This ability supports resolving other issues.

- [x] It would be great to make LLM output (in the current LLM API wrapper) reliably multi-variable, e.g. have formatted object containing file source and other variables, like deciding on next step, or ending iterations in current chat. Perhaps a schema to validate and use ongoing chat to let it retry? This ability supports resolving other issues.

- [ ] runtime environment: running agent under conda clashes with agent's desire to use specific python version, and trying to resolve it installing a new version that never runs due to conda env hardcoded into bash environment. For other runtimes (npm, pnpm) there are similar problems.

- [ ] Python env is 3.11, poetry is installed under mingw64 and it hitches a different python, lower version. Poetry install fails due to python version mismatch to one specified in `pyproject.toml`.

- [x] source code discovery - we need to let agent decide which source files to add to the context for e.g. planning and debug stages (it only gets full file source in code editing stage). It needs to call grep to find files, it needs to search the internet.

- [ ] LLM still writes output instructions directed at human user with step-by-step like "open file, find line..., edit to include...", and occasional placeholders. Perhaps an iterative discovery skill can be used for LLM to trigger with command.

- [ ] LLM misses that dev.yaml file exists in get_file_edits. It is NOT given in files list, but PROJECT section mentions it iin protected files.

- [ ] Debugging agent operation is quite tedious - copious logs, a lot of noise. A log browser app would be very handy.

- [ ] Once there is shell, agent could escape. E.g. debug_error skill produced:  Executing run_shell: {'command': 'echo \'\nname = "Calculator"\nversion = "0.1.0"\ndescription = ""\nauthors = ["Ilya <iva2k@yahoo.com>"]\nreadme = "README.md"\n\n\npython = "^3.11"\npytest = "^7.0"\nruff = "^0.0"\nmypy = "^0.0"\n\n\ninclude = [{ include = "src", from = "src"
}]\n\n\nrequires = ["poetry-core"]\nbuild-backend = "poetry.core.masonry.api"\' > pyproject.toml'}
