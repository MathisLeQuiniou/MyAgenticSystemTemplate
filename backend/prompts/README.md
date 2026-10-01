# Prompts

System prompts live here as Markdown files, one per agent (`<name>.md`).
Load them with `load_prompt("<name>")` or pass `prompt="<name>"` to an agent:
if a file with that name exists it is used, otherwise the string itself is the prompt.

Placeholders like `{placeholder}` are filled by `LLMAgent.format_prompt()` (override it
to inject values from the graph state).
