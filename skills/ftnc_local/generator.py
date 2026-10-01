"""Logique métier du skill FTNC local, sans dépendance Flask.

Bases SQLite ouvertes exclusivement en lecture seule. La génération documentaire
utilise FTNC_Justification_Generator.py fourni avec ce skill.
"""
from __future__ import annotations

import difflib
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTICLE_COLUMNS = {'ref', 'designation', 'issue', 'code_equivalence', 'group'}
BOM_COLUMNS = {'id', 'root_id', 'parent_id', 'parent_article_ref', 'article_ref', 'quantity'}
FTNC_COLUMNS = {'cle', 'programme', 'equipment', 'designation', 'pnr', 'type', 'description', 'quantite', 'responsable', 'disposition', 'reponse', 'date_ouverture', 'date_fermeture', 'status'}


def _config() -> dict[str, Any]:
    path = PROJECT_ROOT / 'config.json'
    if not path.is_file():
        raise FileNotFoundError(f'Configuration introuvable : {path}')
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    section = config.get('skills', {}).get('ftnc_local')
    if not isinstance(section, dict):
        raise TypeError('Configurer skills.ftnc_local dans config.json')
    return section


def _path(key: str, *, required: bool = True) -> Path | None:
    value = _config().get(key)
    if not isinstance(value, str) or not value.strip():
        if required:
            raise ValueError(f'Configurer skills.ftnc_local.{key}')
        return None
    path = Path(value.strip()).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Fichier introuvable ({key}) : {path}')
    return path


def _connect(key: str, required: dict[str, set[str]]) -> sqlite3.Connection:
    path = _path(key)
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for table, columns in required.items():
            actual = {r['name'] for r in conn.execute(f'PRAGMA table_info("{table}")')}
            missing = columns - actual
            if missing:
                raise ValueError(f'{path.name}: colonnes manquantes dans {table}: {", ".join(sorted(missing))}')
        return conn
    except Exception:
        conn.close()
        raise


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ''


def _format_path(path: list[str]) -> str:
    # Convention de app.py : masquer le niveau 0, montrer niveaux 1-3.
    p = [part.strip() for part in path[1:4]]
    if len(p) >= 3 and all(p[:3]):
        return f'{p[0]} - {p[1]} ({p[2]})'
    if len(p) >= 2 and all(p[:2]):
        return f'{p[0]} - {p[1]}'
    return p[0] if p else ''


def _paths(conn: sqlite3.Connection, reference: str) -> list[str]:
    rows = conn.execute('SELECT id, root_id, parent_id, parent_article_ref, article_ref FROM bom').fetchall()
    by_id = {r['id']: r for r in rows}
    result: list[str] = []
    seen_labels: set[str] = set()
    for row in rows:
        if _text(row['article_ref']) != reference:
            continue
        chain: list[str] = []
        visited: set[int] = set()
        current = row
        while current is not None:
            ident = current['id']
            if ident in visited:
                raise ValueError(f'Cycle dans bom pour id={ident}')
            visited.add(ident)
            chain.append(_text(current['article_ref']))
            parent = current['parent_id']
            if parent is None:
                break
            current = by_id.get(parent)
            if current is None:
                raise ValueError(f'Parent bom introuvable : id={parent}')
        chain.reverse()
        root = by_id.get(row['root_id'])
        if root is not None and _text(root['article_ref']) and (not chain or chain[0] != _text(root['article_ref'])):
            chain.insert(0, _text(root['article_ref']))
        label = _format_path(chain)
        if label and label.casefold() not in seen_labels:
            seen_labels.add(label.casefold())
            result.append(label)
    return result


def rechercher_article_ftnc(reference: str) -> dict[str, Any]:
    """Recherche exacte d'un article PDM et de ses chemins Programme/Équipement/LRU."""
    reference = _text(reference)
    if not reference:
        raise ValueError('La référence est obligatoire')
    with closing(_connect('pdm_database_path', {'articles': ARTICLE_COLUMNS, 'bom': BOM_COLUMNS})) as conn:
        row = conn.execute('SELECT ref, designation, issue, code_equivalence, "group" AS article_group FROM articles WHERE ref = ?', (reference,)).fetchone()
        if row is None:
            return {'trouve': False, 'reference': reference, 'message': 'Référence absente de articles.'}
        paths = _paths(conn, reference)
        return {'trouve': True, 'reference': row['ref'], 'designation': _text(row['designation']),
                'issue': _text(row['issue']), 'code_equivalence': _text(row['code_equivalence']),
                'group': _text(row['article_group']), 'programmes': paths}


def rechercher_ftnc_existantes(reference: str) -> dict[str, Any]:
    """Retourne les FTNC dont le PNR correspond exactement, sans tenir compte de la casse."""
    reference = _text(reference)
    if not reference:
        raise ValueError('La référence est obligatoire')
    with closing(_connect('ftnc_database_path', {'FTNC': FTNC_COLUMNS})) as conn:
        rows = conn.execute('SELECT cle, programme, equipment, designation, pnr, type, description, quantite, responsable, disposition, reponse, date_ouverture, date_fermeture, status FROM FTNC WHERE UPPER(TRIM(pnr)) = UPPER(?) ORDER BY cle', (reference,)).fetchall()
        matches = [dict(row) for row in rows]
        return {'reference': reference, 'count': len(matches), 'matches': matches}


def _normalize(value: str) -> str:
    return re.sub(r'[\s\-_]', '', _text(value).casefold())


def suggerer_references_ftnc(recherche: str, limite: int = 5) -> dict[str, Any]:
    """Propose des références proches dans PDM.db (résultats indicatifs, non validés)."""
    q = _normalize(recherche)
    if not q:
        raise ValueError('La recherche est obligatoire')
    if not isinstance(limite, int) or isinstance(limite, bool) or not 1 <= limite <= 20:
        raise ValueError('limite doit être comprise entre 1 et 20')
    with closing(_connect('pdm_database_path', {'articles': ARTICLE_COLUMNS})) as conn:
        rows = conn.execute('SELECT ref, designation, issue FROM articles').fetchall()
    scores = []
    for row in rows:
        ref = _normalize(row['ref'])
        des = _normalize(row['designation'])
        score = max(0.85 if q in ref or ref in q else 0, 0.6 if q in des else 0,
                    difflib.SequenceMatcher(None, q, ref).ratio(),
                    difflib.SequenceMatcher(None, q, des).ratio() * 0.7)
        if score >= 0.4:
            scores.append({'reference': row['ref'], 'designation': row['designation'], 'issue': _text(row['issue']), 'score': round(score, 4)})
    scores.sort(key=lambda item: (-item['score'], item['reference']))
    return {'recherche': recherche, 'suggestions': scores[:limite]}


def _external_generator():
    """Charge le générateur fourni avec le skill, sans chemin de code configurable."""
    from . import FTNC_Justification_Generator as module
    return module


def extraire_fiche_ftnc(chemin_docx: str) -> dict[str, Any]:
    """Extrait les champs d'un DOCX local avec le générateur fourni dans le skill."""
    path = Path(_text(chemin_docx)).expanduser()
    if not _text(chemin_docx) or not path.is_file() or path.suffix.lower() != '.docx':
        raise ValueError('Fournir un chemin local vers un fichier .docx existant')
    data = _external_generator().extract_nq_data(str(path.resolve()))
    if not isinstance(data, dict):
        raise TypeError('extract_nq_data doit retourner un dictionnaire')
    return data


def generer_justification_ftnc(donnees_json: str) -> dict[str, Any]:
    """Génère une justification DOCM, ou DOCX sans macros en cas d'échec du DOCM.

    N'écrit que dans output/ ; ne modifie ni les bases ni les fichiers source.
    """
    try:
        data = json.loads(donnees_json)
    except (TypeError, ValueError) as exc:
        raise ValueError('donnees_json doit contenir un objet JSON valide') from exc
    if not isinstance(data, dict) or not _text(data.get('PNR')) or not _text(data.get('Type FTNC')):
        raise ValueError('Les champs PNR et Type FTNC sont obligatoires')
    module = _external_generator()
    output = PROJECT_ROOT / 'output'
    output.mkdir(parents=True, exist_ok=True)
    # Conserver le comportement de app.py : le nom utilise le niveau Programme,
    # puis Equipment, même si le champ Programme contient une hiérarchie.
    filename_data = dict(data)
    programme = _text(data.get('Programme')).split(' / ')[0].strip()
    if programme:
        match = re.match(r'^\s*(.*?)\s+-\s+(.*?)(?:\s*\((.*?)\))?\s*$', programme)
        if match:
            filename_data['Programme'] = match.group(1).strip()
            if match.group(2).strip():
                filename_data['Equipment'] = match.group(2).strip()
    filename = module.build_output_filename(filename_data, extension='.docm')
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError('Nom de fichier retourné invalide')
    filename = Path(filename).name
    if filename in ('.', '..') or not filename.lower().endswith('.docm'):
        raise ValueError('Le nom de fichier doit se terminer par .docm')
    path = output / filename
    warning = None
    try:
        generated = module.build_docm(output_path=str(path), image_1_path=None, image_2_path=None,
                                      keep_intermediate_docx=False, data=data)
        macro = True
    except Exception as exc:  # noqa: BLE001 — fallback intentionnel : toute erreur COM/Word → DOCX
        warning = f'DOCM indisponible ({exc}); DOCX sans macro généré.'
        path = path.with_suffix('.docx')
        generated = module.build_docx(output_path=str(path), image_1_path=None, image_2_path=None, data=data)
        macro = False
    actual = Path(generated).resolve()
    if actual.parent != output.resolve() or not actual.is_file() or actual.suffix.lower() != ('.docm' if macro else '.docx'):
        raise ValueError('Le générateur n\'a pas produit un fichier valide dans output/')
    return {'fichier': str(actual), 'macro_enabled': macro, 'warning': warning}


def _traiter_fiche_ftnc_detail(
    chemin_docx: str,
    reference_confirmee: str = '',
    type_ftnc: str = '',
    corrections_json: str = '',
    confirmer_generation: bool = False,
) -> dict[str, Any]:
    """Point d'entrée unique, sans état persistant : analyse puis reprise après validation.

    Chaque appel relit le document et les bases. Aucun fichier n'est généré sans
    confirmation explicite de la référence, du type et de la génération.
    """
    from urllib.parse import unquote, urlsplit
    from urllib.request import url2pathname

    source = _text(chemin_docx)
    if not source:
        raise ValueError('Indiquer le chemin local ou le lien file:/// vers la fiche NQ .docx.')
    if source.lower().startswith('file:'):
        parsed = urlsplit(source)
        if parsed.scheme.lower() != 'file' or parsed.query or parsed.fragment:
            raise ValueError('Lien file:/// invalide : aucun paramètre ou fragment autorisé.')
        # Sur Windows, url2pathname convertit /C:/... et les chemins UNC.
        source = url2pathname(unquote(parsed.path))
        if parsed.netloc and parsed.netloc.lower() != 'localhost':
            source = '//' + parsed.netloc + source
    elif '://' in source or source.lower().startswith(('http:', 'https:')):
        raise ValueError('Lien distant non pris en charge : fournir un chemin DOCX local accessible au processus de l’assistant.')

    data = extraire_fiche_ftnc(source)
    original = _text(data.get('PNR'))
    ref = _text(reference_confirmee) or original
    if corrections_json:
        try:
            corrections = json.loads(corrections_json)
        except (ValueError, TypeError) as exc:
            raise ValueError('corrections_json doit être un objet JSON valide.') from exc
        allowed = {'No. NC', 'Programme', 'Designation', 'Quantité', 'No. Série/Lot', 'Description'}
        if not isinstance(corrections, dict) or set(corrections) - allowed or any(not isinstance(v, str) for v in corrections.values()):
            raise ValueError('Corrections autorisées : No. NC, Programme, Designation, Quantité, No. Série/Lot, Description (valeurs texte).')
        data.update({k: v.strip() for k, v in corrections.items()})
    data['PNR'] = ref
    steps = [
        '1. Extraction des champs de la fiche NQ DOCX.',
        '2. Vérification de la référence dans la base articles et de la nomenclature.',
        '3. Recherche des FTNC existantes pour cette référence.',
        '4. Présentation des données et questions avant génération.',
        '5. Génération du document uniquement après validation explicite.',
    ]
    result: dict[str, Any] = {'outil': 'traiter_fiche_ftnc', 'etapes': steps,
                              'chemin_docx': str(Path(source).resolve()), 'donnees': data,
                              'reference_extraite': original, 'reference_utilisee': ref,
                              'type_ftnc': _text(type_ftnc), 'questions': []}
    if not ref:
        result.update(statut='questions', questions=['Aucune référence PNR détectée. Quelle est la référence correcte ?'])
        return result
    article = rechercher_article_ftnc(ref)
    result['article'] = article
    if not article['trouve']:
        result['suggestions'] = suggerer_references_ftnc(ref)['suggestions']
        result.update(statut='questions', questions=['Référence absente de la base articles. Quelle référence faut-il utiliser ?'])
        return result
    precedents = rechercher_ftnc_existantes(ref)
    result['ftnc_existantes'] = precedents
    questions = result['questions']
    if not _text(reference_confirmee):
        questions.append(f'Confirmez-vous la référence PNR {ref} ?')
    if not _text(type_ftnc):
        questions.append('Quel est le Type FTNC à utiliser ?')
    if precedents['count']:
        result['avertissement'] = 'FTNC existantes trouvées : vérifier leur pertinence avant génération.'
    missing = [key for key in ('No. NC', 'Programme', 'Designation', 'Quantité', 'No. Série/Lot', 'Description') if not _text(data.get(key))]
    if missing:
        questions.append('Champs manquants à compléter avant génération : ' + ', '.join(missing) + '.')
    if not confirmer_generation:
        questions.append('Après vérification des données et des FTNC existantes, souhaitez-vous générer la justification ?')
    if questions:
        result['statut'] = 'questions'
        return result
    data['Type FTNC'] = _text(type_ftnc)
    result['generation'] = generer_justification_ftnc(json.dumps(data, ensure_ascii=False))
    result['statut'] = 'termine'
    return result


def traiter_fiche_ftnc(chemin_docx: str, reference_confirmee: str = '',
                       type_ftnc: str = '', corrections_json: str = '',
                       confirmer_generation: bool = False) -> dict:
    """Expose uniquement la question courante ou un lien vers le document produit."""
    detail = _traiter_fiche_ftnc_detail(
        chemin_docx, reference_confirmee, type_ftnc,
        corrections_json, confirmer_generation)
    if detail.get('statut') == 'termine':
        generated = detail['generation']
        path = Path(generated['fichier']).resolve()
        if not path.is_file():
            raise FileNotFoundError('Document genere introuvable.')
        url = path.as_uri()
        return {'statut': 'termine', 'lien': f'[Ouvrir la justification]({url})',
                'fichier_url': url, 'avertissement': generated.get('warning') or ''}
    if detail.get('statut') != 'questions':
        raise ValueError('Statut FTNC inattendu.')
    questions = detail.get('questions') or []
    if not questions:
        raise ValueError('Question manquante pour la reprise du traitement.')
    response = {'statut': 'questions', 'question': questions[0]}
    if not reference_confirmee and detail.get('article', {}).get('trouve'):
        response['message'] = ('Reference detectee : ' + str(detail.get('reference_utilisee') or '')
                               + '. FTNC existantes : '
                               + str((detail.get('ftnc_existantes') or {}).get('count', 0)) + '.')
    if 'suggestions' in detail:
        response['suggestions'] = [{'reference': x.get('reference'), 'designation': x.get('designation')}
                                   for x in detail['suggestions'][:5]]
    return response
