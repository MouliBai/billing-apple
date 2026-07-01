def run_migrations(db):
    """Compatibility hook. DB migrations are currently executed by core.app_shell.DB."""
    if hasattr(db, "_migrate"):
        return db._migrate()
    return None

