# Project working instructions

## Commit, push, and publish

The owner authorizes committing, pushing, and publishing requested or approved
work to this project's GitHub repository unless explicitly instructed otherwise.
After completing and validating a plugin change, commit and push it and publish
a versioned GitHub release with the updated installable
`RainMachine2.indigoPlugin.zip`. Do not ask for repeated confirmation within the
scope of the requested or approved work.

## Validation and packaging

Run `python3 -m unittest discover -s tests` and `git diff --check` before
publishing. Keep the source, plugin version metadata, changelog, and packaged
plugin archive consistent. Exclude `.DS_Store` and Python cache files from the
archive and commits. Use zsh for shell commands.
