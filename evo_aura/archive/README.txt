EvoAura 41-file migration notes

- No EXE conversion was performed.
- Original flat files were copied to migration_backup_41/ before package updates.
- PyQt5 helper files are archived here only and are not imported by the runtime package.
- Runtime package entrypoint: evo_aura/main.py
- Git sync stays isolated in core/git_sync.py.
