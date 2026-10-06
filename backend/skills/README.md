# Skills

Packaged instructions that agents load **on demand** (Anthropic "Agent Skills" format).

```
backend/skills/<name>/
├── SKILL.md          # front matter (name, description) + instructions
├── references/       # optional: docs the instructions point to
└── templates/        # optional: output templates, examples...
```

`SKILL.md`:

```markdown
---
name: my-skill                 # = folder name; lowercase, digits, dashes
description: What it does and WHEN to use it. This is all the agent sees before loading it.
---
Step-by-step instructions. Refer to bundled files by relative path, e.g. references/api.md.
```

Give a skill to an agent, in `BaseGraph.build()`:
`LLMAgent("researcher", prompt="researcher", tools=[...], skills=self.skills.get_many("my-skill"))`
(`get_many("*")` = every skill). The agent gets the catalog (name + description) in its
system prompt and two tools: `load_skill(name)` and `read_skill_file(name, path)`.
Each load shows up in the run trace (SKILL badge).

**Prompt or skill?** The prompt (`backend/prompts/`) says *who* the agent is and is always
loaded. A skill says *how* to do one specific task, is loaded only when needed and can be
shared by several agents. Don't repeat skill content in prompts.

Skills are read-only instructions: bundled scripts are not executed. If a skill needs to
run code, expose that code as a tool (local tool or MCP server).
