import os

import google.generativeai as genai


SYSTEM_PROMPT = """
You are ContextForge, an expert at writing precise AI agent context files.
Your output is always terse, specific, and actionable.
You never write generic advice. Every line must reference something specific about the project given to you.
You write as if you are a senior engineer on the team briefing a new AI agent before a task.
""".strip()


def _get_model():
    """Get configured Gemini model."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Get a free key at aistudio.google.com"
        )
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT
    )


def _build_prompt(ctx, task: str, ide: str) -> str:
    """Build the prompt for Gemini."""
    file_tree_preview = ctx.file_tree[:60]
    if len(ctx.file_tree) > 60:
        file_tree_preview.append(f"... and {len(ctx.file_tree) - 60} more files")

    git_commits = ""
    for commit in ctx.git_log[:8]:
        git_commits += f"  [{commit['date']}] {commit['message']}\n"

    recent_files = "\n".join(f"  {f}" for f in ctx.recent_changed_files) or "  None"

    existing_rules_section = ""
    if ctx.existing_rules:
        existing_rules_section = f"## Existing rules (improve on these)\n{ctx.existing_rules[:1500]}"

    deps = ", ".join(ctx.stack["deps"][:20]) or "none detected"

    return f"""Analyse this project and generate a {ide} rules file for the task described below.

## Project overview
- Language: {ctx.stack["language"]}
- Manifest: {ctx.stack["manifest"] or "none"}
- Key dependencies: {deps}

## File structure
{chr(10).join(file_tree_preview)}

## Recent git commits
{git_commits}

## Recently changed files
{recent_files}

{existing_rules_section}

## Task the developer is about to do
{task}

---

Generate a {ide} rules file that:
1. Gives the AI agent ONLY the context it needs for this specific task — no generic advice
2. Lists the most relevant files it should read first before making changes
3. Calls out known patterns in this codebase the agent should follow (naming, structure, error handling)
4. Flags potential conflict zones — files likely to be affected that the agent must not break
5. States the tech stack constraints clearly (versions, frameworks, patterns already in use)
6. Is under 400 words — tight context beats verbose context

Do NOT include generic best practices. Output ONLY the rules file content. No preamble, no markdown fences.
"""


def generate(ctx, task: str, ide: str = "Cursor") -> str:
    """Generate rules content using Gemini API."""
    model = _get_model()
    prompt = _build_prompt(ctx, task, ide)
    response = model.generate_content(prompt)
    return response.text.strip()
