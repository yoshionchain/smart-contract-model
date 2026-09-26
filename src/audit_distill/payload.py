"""The one textual rendering of a model input, shared by teacher, student and evaluation."""


def render_query(
    check_id: str,
    definition: str,
    scope_kind: str,
    scope_name: str,
    assumptions: list[str],
    source: str,
) -> str:
    scope = "the whole file" if scope_kind == "FILE" else scope_name
    bullets = "\n".join(f"- {text}" for text in assumptions)
    return (
        f"check_id: {check_id}\ndefinition: {definition}\n"
        f"scope: {scope_kind} {scope}\nassumptions:\n{bullets}\n"
        f"source:\n{source}"
    )
