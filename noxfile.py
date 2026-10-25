import nox

nox.options.sessions = ["site"]


@nox.session
def site(session: nox.Session) -> None:
    """Read input JSON, rebuild changed results, and build the MkDocs site."""
    session.install(
        "matplotlib>=3.11.2,<4",
        "numpy>=2.5.4,<3",
        "scipy>=1.18.1,<2",
        "mkdocs>=1.6.1,<2",
    )
    session.run("python", "pipeline.py")
    session.run("python", "sync_docs_assets.py")
    session.run("python", "generate_docs.py")
    session.run("mkdocs", "build", "-f", "docs-site/mkdocs.yml")
