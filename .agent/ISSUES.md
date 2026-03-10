# Issues

This file contains topics to be pondered on and should produce entries in TASKS.md.

- [ ] Installation issue: SSL_CERT_FILE env var is not defined. It should be taken from certifi python package.

- [ ] Python env is 3.11, poetry is installed under mingw64 and it hitches a different python, lower version. Poetry install fails due to python version mismatch to one specified in `pyproject.toml`.

- [x] LLM misses that dev.yaml file exists in get_file_edits. It is NOT given in files list, but PROJECT section mentions it in protected files. To close, verify protected files are listed in context.

- [ ] Debugging agent operation is quite tedious - copious logs, a lot of noise. A log browser app would be very handy.

- [ ] Once there is access to shell, agent could escape. E.g. debug_error skill produced:  Executing run_shell: {'command': 'echo \'\nname = "Calculator"\nversion = "0.1.0"\ndescription = ""\nauthors = ["Ilya <iva2k@yahoo.com>"]\nreadme = "README.md"\n\n\npython = "^3.11"\npytest = "^7.0"\nruff = "^0.0"\nmypy = "^0.0"\n\n\ninclude = [{ include = "src", from = "src"
}]\n\n\nrequires = ["poetry-core"]\nbuild-backend = "poetry.core.masonry.api"\' > pyproject.toml'}
