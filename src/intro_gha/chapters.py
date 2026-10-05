"""The chapter registry: single source for titles, slugs, phases, and book mapping."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chapter:
    """One course chapter and the artifacts that accompany it."""

    num: int
    slug: str
    title: str
    phase: int
    book: str
    depth: str = "Core"
    runtime: str = "Live repo"


PHASES = {
    1: "Foundations",
    2: "Core Mechanics",
    3: "Real Pipelines",
    4: "Security & Operations",
    5: "Extending Actions",
}

CHAPTERS: list[Chapter] = [
    Chapter(0, "essentials_yaml_git_cicd", "Essentials: YAML, Git Refs, CI/CD Vocabulary", 1, "Ch 1", runtime="Offline fixtures"),
    Chapter(1, "why_actions", "Why Actions? Cost vs Scripts and Jenkins", 1, "Ch 1", runtime="Offline fixtures"),
    Chapter(2, "how_actions_works", "How Actions Works: Event, Workflow, Job, Step, Runner", 1, "Ch 2"),
    Chapter(3, "workflow_anatomy", "Workflow YAML Anatomy and Your First Green Check", 1, "Ch 4"),
    Chapter(4, "whats_in_an_action", "What's in an Action: uses, Marketplace, Versioning", 1, "Ch 3"),
    Chapter(5, "runners", "Runners: Hosted, Larger, Self-Hosted, ARC", 1, "Ch 5", runtime="Live repo (guarded)"),
    Chapter(6, "events_and_triggers", "Events and Triggers in Depth", 2, "Ch 4"),
    Chapter(7, "contexts_expressions", "Contexts, Expressions and Conditionals", 2, "Ch 8"),
    Chapter(8, "variables_secrets_environments", "Variables, Secrets, Configuration and Environments", 2, "Ch 6"),
    Chapter(9, "data_outputs_artifacts_caching", "Data Between Steps and Jobs: Outputs, Artifacts, Caching", 2, "Ch 7"),
    Chapter(10, "execution_control", "Execution Control: needs, Matrix, Concurrency, Timeouts", 2, "Ch 8"),
    Chapter(11, "ci_for_python", "CI for Python: Lint, Test, Coverage Matrix", 3, "Ch 4, 7"),
    Chapter(12, "containers_and_ghcr", "Containers, Service Containers and GHCR", 3, "Ch 5, 12"),
    Chapter(13, "continuous_deployment", "Continuous Deployment: Environments and OIDC", 3, "Ch 6, 9", runtime="Live repo (guarded)"),
    Chapter(14, "release_automation", "Release Automation: Tags, Changelogs, Packages", 3, "Ch 12", runtime="Live repo (guarded)"),
    Chapter(15, "token_and_permissions", "GITHUB_TOKEN, Permissions and Least Privilege", 4, "Ch 9"),
    Chapter(16, "supply_chain_security", "Supply-Chain Security: Pinning, Injection, Attestations", 4, "Ch 9"),
    Chapter(17, "monitoring_debugging", "Monitoring, Logging and Debugging", 4, "Ch 10"),
    Chapter(18, "cost_performance_limits", "Cost, Performance and Limits", 4, "Ch 5, 10", runtime="Offline fixtures"),
    Chapter(19, "custom_actions", "Custom Actions: Composite, JavaScript, Docker", 5, "Ch 11"),
    Chapter(20, "reusable_workflows", "Reusable Workflows and Workflow Templates", 5, "Ch 12"),
    Chapter(21, "advanced_techniques", "Advanced Techniques: Dynamic Matrices, github-script, ChatOps", 5, "Ch 13", depth="Optional Deep-Dive"),
    Chapter(22, "migrating_to_actions", "Migrating to Actions: Jenkins, GitLab, Importer", 5, "Ch 14", depth="Optional Deep-Dive", runtime="Offline fixtures"),
    Chapter(23, "capstone", "Capstone: The Full Tally Pipeline", 5, "all"),
]


def chapter_stem(c: Chapter) -> str:
    """Return the shared ``XX_slug`` stem used by chapter, notebook and lab files."""
    return f"{c.num:02d}_{c.slug}"


def map_table() -> str:
    """Render the chapter map as a markdown table (for CLAUDE.md)."""
    rows = [
        "| Ch | Title | Practice | Reference | Script | Book | Depth |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in CHAPTERS:
        s = chapter_stem(c)
        rows.append(
            f"| {c.num:02d} | {c.title} | practice_{c.num:02d}.ipynb | "
            f"lab_{s}.ipynb | lab_{s}.py | {c.book} | {c.depth} |"
        )
    return "\n".join(rows)


if __name__ == "__main__":
    print(map_table())
