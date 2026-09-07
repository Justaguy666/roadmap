"""CLI commands for Knowledge Intelligence: `roadmap knowledge stats`, `index`, and `search`."""

from __future__ import annotations

import json

import typer
from rich.panel import Panel
from rich.table import Table

from roadmap.cli.container import (
    get_knowledge_context,
    get_rag_context,
    initialize_database,
)
from roadmap.cli.display.console import (
    console,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)
from roadmap.config.settings import settings
from roadmap.domain.entities.knowledge import RetrievalFilter

knowledge_app = typer.Typer(help="Knowledge Intelligence, embeddings, and semantic evidence retrieval.")


@knowledge_app.callback(invoke_without_command=True)
def knowledge_default(ctx: typer.Context) -> None:
    """Show knowledge intelligence summary or run subcommands."""
    if ctx.invoked_subcommand is not None:
        return
    stats_cmd()


@knowledge_app.command(name="stats")
def stats_cmd(
    as_json: bool = typer.Option(False, "--json", "-j", help="Output stats in JSON format"),
) -> None:
    """Display knowledge indexing and vector storage statistics."""
    initialize_database()

    with get_knowledge_context() as (evidence_repo, source_repo, knowledge_repo, _):
        doc_count = knowledge_repo.count_documents()
        chunk_count = knowledge_repo.count_chunks()
        embedding_count = knowledge_repo.count_embeddings()
        evidence_count = len(evidence_repo.list_all(limit=10000))
        source_count = len(source_repo.list_all(limit=10000))

    if as_json:
        data = {
            "sources": source_count,
            "evidence": evidence_count,
            "knowledge_documents": doc_count,
            "knowledge_chunks": chunk_count,
            "embedding_records": embedding_count,
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimension": settings.embedding_dimension,
        }
        console.print(json.dumps(data, indent=2))
        return

    print_header("Knowledge Intelligence — Index & Storage Statistics")

    table = Table(border_style="cyan")
    table.add_column("Dimension", style="bold white")
    table.add_column("Count / Setting", justify="center", style="green")
    table.add_column("Description", style="dim")

    table.add_row("Canonical Sources", str(source_count), "Crawled web pages and publications")
    table.add_row("Canonical Evidence", str(evidence_count), "Discrete claims extracted from sources")
    table.add_row("Knowledge Documents", str(doc_count), "Documents synchronized from evidence")
    table.add_row("Knowledge Chunks", str(chunk_count), f"Chunk size ~{settings.knowledge_chunk_size} chars")
    table.add_row("Embedding Vectors", str(embedding_count), f"{settings.embedding_model} ({settings.embedding_dimension}d)")
    table.add_row("Embedding Provider", settings.embedding_provider, "Configured via ROADMAP_EMBEDDING_PROVIDER")

    console.print(table)
    console.print()
    if doc_count == 0 and evidence_count > 0:
        print_info("Evidence is available but unindexed. Run [bold]roadmap knowledge index[/bold] to build index.")


@knowledge_app.command(name="index")
def index_cmd(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-indexing and re-embedding of all canonical evidence",
    ),
) -> None:
    """Index canonical research evidence into deterministic vector chunks."""
    initialize_database()

    print_header("Knowledge Intelligence — Indexing Pipeline")
    console.print(f"  Provider: [bold]{settings.embedding_provider}[/bold] | Model: [bold]{settings.embedding_model}[/bold] ({settings.embedding_dimension}d)")
    console.print(f"  Chunk Size: {settings.knowledge_chunk_size} chars | Overlap: {settings.knowledge_chunk_overlap} chars")
    console.print()

    with (
        console.status("[bold cyan]Processing canonical evidence, chunking, and generating embeddings...[/bold cyan]"),
        get_knowledge_context() as (_, _, _, indexing_service),
    ):
        try:
            summary = indexing_service.index_all_evidence(force=force)
        except Exception as exc:
            print_error(f"Knowledge indexing failed: {exc}")
            raise typer.Exit(1) from exc

    docs = summary["documents"]
    chunks = summary["chunks"]
    embs = summary["embeddings"]

    if docs == 0 and not force:
        print_info("All canonical evidence is already indexed and current. Use [bold]--force[/bold] to re-index.")
    else:
        print_success("Knowledge indexing completed successfully!")
        console.print(f"  Documents Processed: [bold]{docs}[/bold]")
        console.print(f"  Chunks Created:      [bold]{chunks}[/bold]")
        console.print(f"  Embeddings Saved:    [bold]{embs}[/bold]")
    console.print()


@knowledge_app.command(name="search")
def search_cmd(
    query: str = typer.Argument(help="Natural language query to search"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to return"),
    threshold: float | None = typer.Option(None, "--threshold", "-t", help="Minimum similarity threshold (0.0 - 1.0)"),
    skill: str | None = typer.Option(None, "--skill", "-s", help="Filter by skill name"),
    domain: str | None = typer.Option(None, "--domain", "-d", help="Filter by source domain"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output results in JSON format"),
) -> None:
    """Search knowledge index using semantic vector similarity."""
    initialize_database()

    filters = RetrievalFilter(
        skill_names=[skill] if skill else [],
        domain=domain,
        min_similarity=threshold,
    )

    with get_rag_context() as (rag_service, _, _):
        context = rag_service.retrieve_context(
            query=query,
            top_k=top_k,
            filters=filters,
        )

    if as_json:
        data = {
            "query": context.query,
            "retrieved_count": len(context.blocks),
            "results": [
                {
                    "evidence_id": b.evidence_id,
                    "source_title": b.source_title,
                    "source_url": b.source_url,
                    "is_authoritative": b.is_authoritative,
                    "excerpt": b.excerpt,
                    "associated_skills": b.associated_skills,
                }
                for b in context.blocks
            ],
        }
        console.print(json.dumps(data, indent=2))
        return

    print_header(f"Semantic Search Results: \"{query}\"")

    if not context.blocks:
        print_warning("No matching evidence found meeting similarity criteria.")
        print_info("Try adjusting search terms, lowering threshold, or running [bold]roadmap knowledge index[/bold].")
        return

    for idx, block in enumerate(context.blocks, start=1):
        auth_tag = "[bold green]AUTHORITATIVE[/bold green]" if block.is_authoritative else "[dim]Standard[/dim]"
        title = block.source_title or "Untitled Source"

        header_str = f"#{idx} [bold cyan]{block.evidence_id}[/bold cyan] ({auth_tag})"
        body_lines = [
            f"[bold white]Source:[/bold white] {title}",
        ]
        if block.source_url:
            body_lines.append(f"[bold white]URL:[/bold white] [dim]{block.source_url}[/dim]")
        if block.associated_skills:
            body_lines.append(f"[bold white]Skills:[/bold white] {', '.join(block.associated_skills)}")
        body_lines.append(f"\n[bold white]Relevant Excerpt:[/bold white]\n{block.excerpt}")

        console.print(
            Panel(
                "\n".join(body_lines),
                title=header_str,
                border_style="cyan",
            )
        )
    console.print()
