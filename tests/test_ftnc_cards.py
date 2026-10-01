"""Tests de non-regression du rendu FTNC, sans lecture des classeurs metier."""
import unittest

from src.ui.widgets.ftnc_card_parser import parse_ftnc_result


class FtncCardsParserTests(unittest.TestCase):
    def test_liste_preserves_sections_order_counts_and_unknown_quantity(self):
        text = (
            "FTNC EN COURS\n" + "=" * 40 + "\n"
            "1. MWB1234567890 🚩 | Rafale B/C | En cours | Priorité : Urgent\n\n"
            "Nombre de FTNC du planner : 1\n\n"
            "NOUVELLES FTNC À AJOUTER AU PLANNER\n" + "-" * 40 + "\n"
            "2. [VLB1234567891] ATL2 - Support (REF-A) - 2 pièces\n"
            "Description de vérification\nDate de début : 01/09/26\n\n"
            "Nombre de FTNC en cours dans le suivi €uro : 1"
        )
        parsed = parse_ftnc_result(text, "Liste")
        self.assertEqual(len(parsed["sections"]), 2)
        planner = parsed["sections"][0]["cards"][0]
        suivi = parsed["sections"][1]["cards"][0]
        self.assertEqual(planner["reference"], "MWB1234567890")
        self.assertEqual(planner["quantite"], "")
        self.assertEqual(suivi["quantite"], "2")
        self.assertEqual(suivi["description"], "Description de vérification")
        self.assertEqual(len(parsed["counts"]), 2)

    def test_details_keeps_multiple_sources_and_missing_quantity(self):
        text = (
            'DÉTAILS DE LA FTNC "1234567890"\n' + "=" * 40 + "\n"
            "Correspondance 1/2\nSource : FTNC.xlsx / planner\n"
            "Référence FTNC : MWB1234567890\nProgramme : ATL2\n"
            "Statut : En cours\nPriorité : Moyen\n\n"
            "Correspondance 2/2\nSource : Suivi des FTNC €uro.xlsx\n"
            "Référence FTNC : MWB1234567890\nProgramme : ATL2\n"
            "Statut : En cours\nType : Structure\nPôle : PPM\n"
            "Pièce : Support\nRéférence pièce : REF-A\nQuantité : 3\n"
            "Date de début : 01/09/26\nDescription : Description de vérification"
        )
        cards = parse_ftnc_result(text, "Details")["sections"][0]["cards"]
        self.assertEqual(len(cards), 2)
        self.assertNotIn("quantite", cards[0])
        self.assertEqual(cards[1]["quantite"], "3")
        self.assertEqual(cards[1]["source"], "Suivi des FTNC €uro.xlsx")

    def test_empty_and_unrecognized_are_not_invented(self):
        text = 'Aucune FTNC trouvée pour la référence "X".'
        parsed = parse_ftnc_result(text, "Details")
        self.assertEqual(parsed["message"], text)
        self.assertFalse(parsed["sections"])
        self.assertEqual(parse_ftnc_result("Format inconnu", "Liste")["message"], "Format inconnu")

    def test_malformed_list_falls_back_to_full_text(self):
        text = "FTNC EN COURS\n1. ligne illisible\nNombre de FTNC du planner : 1"
        parsed = parse_ftnc_result(text, "Liste")
        self.assertEqual(parsed["message"], text)
        self.assertFalse(parsed["sections"])

    def test_empty_planner_keeps_messages_and_counts(self):
        text = (
            "FTNC EN COURS\n" + "=" * 40 + "\n"
            "Aucune FTNC ne correspond aux critères demandés.\n"
            "Nombre de FTNC du planner : 0\n"
            "Aucune nouvelle FTNC à ajouter au planner.\n"
            "Nombre de FTNC en cours dans le suivi €uro : 0"
        )
        parsed = parse_ftnc_result(text, "Liste")
        self.assertEqual(len(parsed["sections"][0]["messages"]), 2)
        self.assertEqual(len(parsed["counts"]), 2)


if __name__ == "__main__":
    unittest.main()
