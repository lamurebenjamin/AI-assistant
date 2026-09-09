# -*- coding: utf-8 -*-
"""Moteur de rendu et conversion Markdown vers HTML et texte parlé."""

import base64
import html
import re


def format_inline_markdown(text: str) -> str:
    """Met en forme les éléments Markdown inline (liens, gras, italique, code)."""
    escaped = html.escape(text, quote=False)

    # Les liens sont protégés avant les substitutions Markdown d'emphase.
    # Sans cette protection, les underscores présents dans le libellé ou
    # dans l'URI file:/// sont interprétés comme _italique_ et injectent
    # des balises <i> à l'intérieur de l'attribut href.
    protected_links = []

    def protect_link(link_html):
        token = f"\x00PROTECTEDLINKTOKEN{len(protected_links)}X\x00"
        protected_links.append(link_html)
        return token

    def source_link(match):
        filename = match.group(1).strip().lstrip("-•* ").strip()
        page = match.group(2)
        encoded_name = base64.urlsafe_b64encode(
            filename.encode("utf-8")
        ).decode("ascii").rstrip("=")
        return protect_link(
            f'<a href="source:{page}:{encoded_name}" '
            f'style="color:#1565C0; text-decoration:underline;">'
            f"{filename} • p. {page}</a>"
        )

    escaped = re.sub(
        r"([^<>\n/\\]+?\.pdf)\s*[•-]\s*(?:p(?:age)?\.?\s*)?(\d+)",
        source_link,
        escaped,
        flags=re.IGNORECASE,
    )

    def file_link(match):
        label = match.group(1)
        uri = match.group(2)
        return protect_link(
            f'<a href="{uri}" '
            f'style="color:#1565C0; text-decoration:underline;">'
            f"{label}</a>"
        )

    escaped = re.sub(
        r"\[([^\]\n]+)\]\((file:///[^)\s]+)\)",
        file_link,
        escaped,
        flags=re.IGNORECASE,
    )
    escaped = re.sub(
        r"`([^`\n]+)`",
        r'<code style="background-color:rgba(0,0,0,18); padding:1px 4px; border-radius:4px; font-family:Consolas, monospace;">\1</code>',
        escaped,
    )
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"<i>\1</i>", escaped)
    escaped = escaped.replace("**", "").replace("__", "")

    for index, link_html in enumerate(protected_links):
        escaped = escaped.replace(
            f"\x00PROTECTEDLINKTOKEN{index}X\x00",
            link_html,
        )
    return escaped


def markdown_to_html(markdown_text: str) -> str:
    """Convertit un texte au format Markdown en HTML compatible avec les widgets Qt."""
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output = []
    paragraph = []
    list_type = None
    in_code = False
    code_lines = []

    def close_paragraph():
        if paragraph:
            joined = "<br>".join(format_inline_markdown(line) for line in paragraph)
            output.append(f'<p style="margin:0 0 8px 0;">{joined}</p>')
            paragraph.clear()

    def close_list():
        nonlocal list_type
        if list_type:
            output.append(f"</{list_type}>")
            list_type = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            close_paragraph()
            close_list()
            if in_code:
                code = html.escape("\n".join(code_lines), quote=False)
                output.append(
                    '<pre style="margin:4px 0 8px 0; padding:8px; background-color:rgba(0,0,0,18); border-radius:6px; white-space:pre-wrap; font-family:Consolas, monospace;">'
                    f"{code}</pre>"
                )
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            close_paragraph()
            close_list()
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading:
            close_paragraph()
            close_list()
            size = {1: 18, 2: 16, 3: 14}[len(heading.group(1))]
            title = format_inline_markdown(heading.group(2))
            output.append(
                f'<div style="font-size:{size}px; font-weight:600; margin:6px 0 4px 0;">{title}</div>'
            )
            continue
        bullet = re.match(r"^[-+*]\s+(.+)$", stripped)
        numbered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if bullet or numbered:
            close_paragraph()
            wanted_type = "ul" if bullet else "ol"
            if list_type != wanted_type:
                close_list()
                list_type = wanted_type
                output.append(f'<{list_type} style="margin:2px 0 8px 0; padding-left:22px;">')
            item = bullet.group(1) if bullet else numbered.group(1)
            output.append(f'<li style="margin:2px 0;">{format_inline_markdown(item)}</li>')
            continue
        close_list()
        paragraph.append(line)

    if in_code:
        code = html.escape("\n".join(code_lines), quote=False)
        output.append(
            '<pre style="margin:4px 0 8px 0; padding:8px; background-color:rgba(0,0,0,18); border-radius:6px; white-space:pre-wrap; font-family:Consolas, monospace;">'
            f"{code}</pre>"
        )
    close_paragraph()
    close_list()
    return "".join(output)


def markdown_to_spoken_text(text: str) -> str:
    """Convertit une réponse Markdown en texte naturel avant synthèse vocale."""
    if not text:
        return ""

    spoken = html.unescape(str(text)).replace("\r\n", "\n").replace("\r", "\n")

    # Conserve le contenu des blocs de code, mais supprime les délimiteurs et le langage
    spoken = re.sub(
        r"```[^\n]*\n?(.*?)```",
        lambda match: "\n" + match.group(1).strip() + "\n",
        spoken,
        flags=re.DOTALL,
    )
    spoken = re.sub(
        r"~~~[^\n]*\n?(.*?)~~~",
        lambda match: "\n" + match.group(1).strip() + "\n",
        spoken,
        flags=re.DOTALL,
    )

    # Les images deviennent leur texte alternatif et les liens ne gardent que leur libellé
    spoken = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", spoken)
    spoken = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", spoken)
    spoken = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", spoken)
    spoken = re.sub(r"^\s*\[[^\]]+\]:\s*\S+.*$", "", spoken, flags=re.MULTILINE)

    # Retire les balises HTML éventuelles, sans supprimer leur contenu
    spoken = re.sub(r"<br\s*/?>", "\n", spoken, flags=re.IGNORECASE)
    spoken = re.sub(r"<[^>]+>", " ", spoken)

    # Supprime les séparateurs de tableaux Markdown et transforme les cellules en pauses
    spoken = re.sub(
        r"^\s*\|?\s*:?-{3,}:?(?:\s*\|\s*:?-{3,}:?)+\s*\|?\s*$",
        "",
        spoken,
        flags=re.MULTILINE,
    )
    spoken = re.sub(r"(?m)^\s*\|\s*", "", spoken)
    spoken = re.sub(r"(?m)\s*\|\s*$", "", spoken)
    spoken = spoken.replace("|", ", ")

    # Nettoie les marqueurs de titres, citations, listes et cases à cocher
    spoken = re.sub(r"^\s{0,3}#{1,6}\s+", "", spoken, flags=re.MULTILINE)
    spoken = re.sub(r"^\s{0,3}>+\s?", "", spoken, flags=re.MULTILINE)
    spoken = re.sub(r"^\s*[-+*]\s+\[[ xX]\]\s+", "", spoken, flags=re.MULTILINE)
    spoken = re.sub(r"^\s*[-+*]\s+", "", spoken, flags=re.MULTILINE)
    spoken = re.sub(r"^\s*\d+[.)]\s+", "", spoken, flags=re.MULTILINE)
    spoken = re.sub(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", "", spoken, flags=re.MULTILINE)

    # Retire les marqueurs de mise en forme tout en conservant les mots
    spoken = re.sub(r"`([^`]+)`", r"\1", spoken)
    spoken = re.sub(r"(\*\*\*|___)(.+?)\1", r"\2", spoken, flags=re.DOTALL)
    spoken = re.sub(r"(\*\*|__)(.+?)\1", r"\2", spoken, flags=re.DOTALL)
    spoken = re.sub(r"(?<!\w)([*_])([^\n]+?)\1(?!\w)", r"\2", spoken)
    spoken = re.sub(r"~~(.+?)~~", r"\1", spoken, flags=re.DOTALL)
    spoken = (
        spoken.replace("\\*", "*")
        .replace("\\_", "_")
        .replace("\\#", "#")
        .replace("\\`", "`")
    )

    # Évite de prononcer les derniers caractères Markdown isolés
    spoken = re.sub(r"[*`~]+", "", spoken)
    spoken = re.sub(r"(?m)^\s*#+\s*$", "", spoken)
    spoken = re.sub(r"[ \t]+", " ", spoken)
    spoken = re.sub(r"\s*\n\s*", ". ", spoken)
    spoken = re.sub(r"(?:\.\s*){2,}", ". ", spoken)
    return spoken.strip(" .")
