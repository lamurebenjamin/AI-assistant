"""Formatage partagé des statuts visuels des blocs d'activité."""


def format_duration(seconds: float) -> str:
    """Formate une durée courte pour les en-têtes de raisonnement et d'outils."""
    diff = max(0.5, float(seconds))
    if diff < 1:
        return "1s"
    if diff < 60:
        return f"{int(diff)}s"
    minutes = int(diff // 60)
    remaining_seconds = int(diff % 60)
    return (
        f"{minutes}m {remaining_seconds}s"
        if remaining_seconds > 0
        else f"{minutes}m"
    )


def format_thinking_status(duration_seconds: float) -> str:
    """Retourne le statut final affiché pour un bloc de raisonnement."""
    return f"Réflexion de {max(0, round(duration_seconds))}s"


def format_tool_group_status(
    step_count: int,
    is_running: bool,
    duration_text: str = "",
) -> str:
    """Retourne le statut d'un groupe d'exécution d'outils."""
    if is_running:
        label = "step" if step_count == 1 else "steps"
        return f"Working on {step_count} {label}"
    completed_word = "étape complétée" if step_count == 1 else "étapes complétée"
    return f"{step_count} {completed_word} en {duration_text}"
