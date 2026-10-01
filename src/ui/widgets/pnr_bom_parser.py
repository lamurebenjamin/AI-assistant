"""Transforme le résultat texte du skill PNR en arborescence visuelle."""
from __future__ import annotations

import re

_SECTION = re.compile(r"^Nomenclature \d+ \(bom\.id=\d+\) :$")
_LINE = re.compile(r"^(?P<indent> *)Niveau (?P<level>\d+) : (?P<label>.*)$")
_MARKER = re.compile(r"\s*<- reference recherchee$")
_ARTICLE = re.compile(r"^(?P<designation>.*) \((?P<reference>[^()]*)\)$")
_REVISION = re.compile(r"\s+Rev\.[^)]*$")


def _display_label(raw: str) -> str:
    """Convertit 'Désignation (REF Rev.A)' en 'REF - Désignation'."""
    match = _ARTICLE.fullmatch(raw)
    if match is None:
        return raw  # Conserver un message imprévu sans inventer une référence.
    reference = _REVISION.sub("", match.group("reference")).strip()
    return f"{reference} - {match.group('designation')}"


def parse_pnr_result(text: str) -> dict:
    """Conserve l'arbre des chemins menant au PNR, tous niveaux confondus."""
    if not isinstance(text, str):
        raise TypeError("Le résultat PNR doit être du texte")
    result: dict = {"sections": [], "messages": []}
    current: dict | None = None
    stack: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("Référence recherchée :", "Reference recherchee :")):
            continue
        if _SECTION.fullmatch(line):
            current = {"nodes": [], "messages": []}
            result["sections"].append(current)
            stack = []
            continue
        match = _LINE.fullmatch(raw)
        if match and current is not None:
            level = int(match.group("level"))
            if len(match.group("indent")) != 2 * level:
                raise ValueError("Indentation PNR inattendue")
            raw_label = match.group("label")
            found = bool(_MARKER.search(raw_label))
            raw_label = _MARKER.sub("", raw_label)
            article = _ARTICLE.fullmatch(raw_label)
            designation = article.group("designation") if article else None
            label = _display_label(raw_label)
            if level == 3 and article and len(stack) >= 3:
                level_1 = stack[1].get("designation")
                level_2 = stack[2].get("designation")
                if level_1 and level_2:
                    reference = _REVISION.sub("", article.group("reference")).strip()
                    label = (
                        f"{reference} - {designation} "
                        f"({level_1} - {level_2})"
                    )
            node = {"level": level, "label": label, "designation": designation,
                    "found": found, "children": []}
            if level == 0:
                current["nodes"].append(node)
                stack = [node]
            else:
                if len(stack) < level:
                    raise ValueError("Niveau PNR sans parent")
                stack[level - 1]["children"].append(node)
                stack = stack[:level] + [node]
        elif current is not None:
            current["messages"].append(line)
        else:
            result["messages"].append(line)
    return result


def visible_nodes(section: dict) -> list[dict]:
    """Masque les niveaux 0-2, sauf si le PNR est lui-même à ce niveau."""
    def filter_node(node: dict) -> list[dict]:
        children = [item for child in node["children"] for item in filter_node(child)]
        if node["level"] < 3 and not node["found"]:
            return children
        return [{**node, "children": children}]
    return [item for node in section["nodes"] for item in filter_node(node)]
