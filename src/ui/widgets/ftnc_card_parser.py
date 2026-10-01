"""Décode le résultat textuel FTNC et extrait la référence de Details."""
import json
import re


def normalize_ftnc_text(value):
    text = str(value or '').strip()
    for _ in range(2):
        if not (text.startswith('"') and text.endswith('"')):
            break
        try:
            decoded = json.loads(text)
        except (ValueError, TypeError):
            break
        if not isinstance(decoded, str):
            break
        text = decoded.strip()
    return text


def identify_ftnc_output(value):
    text = normalize_ftnc_text(value)
    if text.startswith('FTNC EN COURS\n') and 'Nombre de FTNC du planner : ' in text:
        return 'Liste'
    if text.startswith('DÉTAILS DE LA FTNC "') and '\nSource : ' in text:
        return 'Details'
    if text.startswith('Aucune FTNC trouvée pour la référence "'):
        return 'Details'
    return ''


def ftnc_reference_from_output(value):
    text = normalize_ftnc_text(value)
    match = re.match(r'(?:DÉTAILS DE LA FTNC|Aucune FTNC trouvée pour la référence) "([^"]+)"', text)
    return match.group(1) if match else ''


def parse_ftnc_result(value, tool_name):
    """Compatibilité du parseur texte historique; non utilisé par la grille Excel."""
    raw = normalize_ftnc_text(value)
    sections, counts = [], []
    if tool_name == 'Liste' and identify_ftnc_output(raw) == 'Liste':
        current = None
        lines = raw.splitlines()
        index = 0
        invalid = False
        while index < len(lines):
            line = lines[index].strip()
            if line == 'FTNC EN COURS':
                current = {'title': 'FTNC du planner', 'cards': [], 'messages': []}
                sections.append(current)
            elif line == 'NOUVELLES FTNC À AJOUTER AU PLANNER':
                current = {'title': 'À ajouter au planner', 'cards': [], 'messages': []}
                sections.append(current)
            elif line.startswith('Nombre de FTNC '):
                counts.append(line)
            elif line.startswith('Aucune '):
                if current is None:
                    current = {'title': 'FTNC', 'cards': [], 'messages': []}
                    sections.append(current)
                current['messages'].append(line)
            elif re.match(r'^\d+\. ', line):
                if current is None:
                    invalid = True
                elif current['title'] == 'FTNC du planner':
                    parts = line.split(' | ')
                    if len(parts) != 4 or not parts[3].startswith('Priorité : '):
                        invalid = True
                    else:
                        prefix = re.sub(r'^\d+\. ', '', parts[0]).strip()
                        reference = prefix.rsplit(' ', 1)[0].strip()
                        if not reference:
                            invalid = True
                        else:
                            current['cards'].append({
                                'reference': reference, 'programme': parts[1],
                                'statut': parts[2], 'priorite': parts[3][len('Priorité : '):],
                                'source': 'FTNC.xlsx / planner', 'quantite': '',
                            })
                else:
                    match = re.match(
                        r'^\d+\. \[(?P<reference>[^]]+)\] (?P<programme>.+?) - '
                        r'(?P<designation>.*) \((?P<reference_piece>[^()]*)\) - '
                        r'(?P<quantite>.*?) pièces?$', line, re.IGNORECASE)
                    if not match:
                        invalid = True
                    else:
                        card = match.groupdict()
                        card['source'] = 'Suivi des FTNC €uro.xlsx'
                        card['statut'] = 'En cours'
                        index += 1
                        description = []
                        while index < len(lines) and not lines[index].startswith('Date de début : '):
                            description.append(lines[index].strip())
                            index += 1
                        if index >= len(lines):
                            invalid = True
                        else:
                            card['date_debut'] = lines[index].split(' : ', 1)[1]
                        card['description'] = '\n'.join(x for x in description if x)
                        current['cards'].append(card)
            index += 1
        for count in counts:
            match = re.fullmatch(r'Nombre de FTNC du planner : (\d+)', count)
            if match and (not sections or len(sections[0]['cards']) != int(match.group(1))):
                invalid = True
        if invalid:
            return {'sections': [], 'counts': [], 'message': raw}
    elif tool_name == 'Details' and identify_ftnc_output(raw) == 'Details':
        if raw.startswith('Aucune FTNC trouvée'):
            return {'sections': [], 'counts': [], 'message': raw}
        section = {'title': 'Détails FTNC', 'cards': [], 'messages': []}
        sections.append(section)
        card = None
        fields = {'Référence FTNC': 'reference', 'Programme': 'programme',
                  'Statut': 'statut', 'Priorité': 'priorite', 'Type': 'type',
                  'Pôle': 'pole', 'Pièce': 'designation',
                  'Référence pièce': 'reference_piece', 'Quantité': 'quantite',
                  'Date de début': 'date_debut', 'Description': 'description'}
        for line in raw.splitlines():
            if line.startswith('Source : '):
                card = {'source': line[len('Source : '):]}
                section['cards'].append(card)
            elif card is not None and ' : ' in line:
                label, text = line.split(' : ', 1)
                if label in fields:
                    card[fields[label]] = text
    if not any(s['cards'] or s['messages'] for s in sections):
        return {'sections': [], 'counts': [], 'message': raw}
    return {'sections': sections, 'counts': counts, 'message': ''}
