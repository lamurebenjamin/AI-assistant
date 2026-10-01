"""Recherche PNR, remontée à la racine et chemins jusqu'à la référence."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _database_path() -> Path:
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration introuvable : {config_path}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        value = config["skills"]["pnr"]["database_path"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("config.json invalide : renseigner skills.pnr.database_path") from exc
    if not isinstance(value, str) or not value.strip():
        raise ValueError("config.json : skills.pnr.database_path doit être un chemin non vide")
    path = Path(value.strip()).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Base PNR introuvable : {path}")
    return path


def _validate_schema(conn: sqlite3.Connection) -> None:
    required = {
        "articles": {"ref", "designation", "issue"},
        "bom": {"id", "parent_id", "article_ref"},
    }
    for table, columns in required.items():
        actual = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        missing = columns - actual
        if missing:
            raise ValueError(f"PNR.db : colonnes absentes de {table} : {', '.join(sorted(missing))}")


def _label(conn: sqlite3.Connection, reference: str) -> str:
    row = conn.execute(
        "SELECT designation, issue FROM articles WHERE ref = ?", (reference,)
    ).fetchone()
    if row is None:
        return f"Désignation inconnue ({reference} Rev.?)"
    issue = str(row["issue"]).strip() if row["issue"] is not None else ""
    return f"{row['designation']} ({reference} Rev.{issue or '?'})"


def _ancestor_path(conn: sqlite3.Connection, occurrence_id: int) -> list[sqlite3.Row]:
    """Chemin racine -> occurrence, avec détection des cycles et parents absents."""
    path: list[sqlite3.Row] = []
    seen: set[int] = set()
    current = occurrence_id
    while True:
        if current in seen:
            raise ValueError(f"Cycle détecté dans bom depuis id={occurrence_id}")
        seen.add(current)
        row = conn.execute(
            "SELECT id, parent_id, article_ref FROM bom WHERE id = ?", (current,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Parent introuvable dans bom : id={current}")
        path.append(row)
        if row["parent_id"] is None:
            path.reverse()
            return path
        current = row["parent_id"]


def rechercher_reference(reference: str) -> str:
    """Renvoie les chemins racine -> référence, sans limiter la profondeur.

    Le résultat reste au format texte de l'outil existant. Le widget Qt masque
    les niveaux 0-2 et les révisions, mais peut afficher tous les niveaux
    suivants jusqu'à la référence effectivement trouvée.
    """
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("La référence doit être une chaîne non vide")
    reference = reference.strip()
    path = _database_path()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        _validate_schema(conn)
        occurrences = conn.execute(
            "SELECT id FROM bom WHERE article_ref = ? ORDER BY id", (reference,)
        ).fetchall()
        if not occurrences:
            article = conn.execute(
                "SELECT ref FROM articles WHERE ref = ?", (reference,)
            ).fetchone()
            if article is None:
                return f"Référence {reference} introuvable dans articles et bom."
            return f"{_label(conn, reference)}\nAucune occurrence dans bom."

        # Ne retenir que les chemins qui aboutissent à la référence demandée.
        # Une même ligne de BOM peut appartenir à plusieurs chemins : l'afficher
        # une seule fois par nomenclature (identifiant de racine).
        roots: dict[int, dict[int, tuple[int, sqlite3.Row]]] = {}
        matched_ids: dict[int, set[int]] = {}
        for occurrence in occurrences:
            chain = _ancestor_path(conn, occurrence["id"])
            root_id = chain[0]["id"]
            nodes = roots.setdefault(root_id, {})
            matched_ids.setdefault(root_id, set()).add(occurrence["id"])
            for level, node in enumerate(chain):
                nodes[node["id"]] = (level, node)

        lines = [f"Référence recherchée : {reference}"]
        for index, root_id in enumerate(sorted(roots), 1):
            lines.extend(("", f"Nomenclature {index} (bom.id={root_id}) :"))
            nodes = roots[root_id]
            children: dict[int, list[int]] = {}
            for node_id, (_, node) in nodes.items():
                parent_id = node["parent_id"]
                if parent_id is not None:
                    children.setdefault(parent_id, []).append(node_id)

            def visit(
                node_id: int,
                _nodes: dict = nodes,
                _root_id: int = root_id,
                _children: dict = children,
            ) -> None:
                level, node = _nodes[node_id]
                marker = "  <- reference recherchee" if node_id in matched_ids[_root_id] else ""
                lines.append(
                    f"{'  ' * level}Niveau {level} : "
                    f"{_label(conn, node['article_ref'])}{marker}"
                )
                for child_id in sorted(_children.get(node_id, [])):
                    visit(child_id)

            visit(root_id)
        return "\n".join(lines)
