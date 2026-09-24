"""Tests unitaires pour la configuration dynamique et la sécurité du skill FTNC."""

import os
import tempfile
import unittest
from pathlib import Path

from skills.ftnc.generator import _get_ftnc_config, _verifier
from src.config.manager import load_config
from src.config.schema import DEFAULT_CONFIG


class FtncDynamicConfigTests(unittest.TestCase):
    def test_schema_includes_skills_ftnc_defaults(self):
        """Vérifie que DEFAULT_CONFIG et load_config exposent la section skills.ftnc."""
        self.assertIn("skills", DEFAULT_CONFIG)
        self.assertIn("ftnc", DEFAULT_CONFIG["skills"])
        self.assertEqual(DEFAULT_CONFIG["skills"]["ftnc"]["feuille_ftnc"], "Données consolidées")
        self.assertEqual(DEFAULT_CONFIG["skills"]["ftnc"]["feuille_suivi_euro"], "SUIVI")

        cfg = load_config()
        self.assertIn("skills", cfg)
        self.assertIn("ftnc", cfg["skills"])

    def test_verifier_raises_when_unconfigured(self):
        """Vérifie qu'un chemin non configuré (None ou vide) lève une FileNotFoundError explicite."""
        with self.assertRaises(FileNotFoundError) as ctx:
            _verifier(None, "du test")
        self.assertIn("n'est pas configuré", str(ctx.exception))
        self.assertIn("config.json", str(ctx.exception))

    def test_verifier_raises_when_file_not_found(self):
        """Vérifie qu'un fichier inexistant lève une FileNotFoundError avec le chemin."""
        fictional_path = Path("C:/chemin/inexistant_12345/FTNC.xlsx")
        with self.assertRaises(FileNotFoundError) as ctx:
            _verifier(fictional_path, "du planner")
        self.assertIn("est introuvable", str(ctx.exception))
        self.assertIn("inexistant_12345", str(ctx.exception))

    def test_verifier_succeeds_when_file_exists(self):
        """Vérifie que _verifier retourne le chemin quand le fichier existe."""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            verified = _verifier(tmp_path, "test_file")
            self.assertEqual(verified, tmp_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_env_var_override(self):
        """Vérifie que les variables d'environnement prennent le pas sur la configuration."""
        os.environ["FTNC_FICHIER_PLANNER"] = "C:/tmp/mon_planner.xlsx"
        os.environ["FTNC_FEUILLE_PLANNER"] = "MaFeuille"
        try:
            cfg = _get_ftnc_config()
            self.assertEqual(cfg["feuille_ftnc"], "MaFeuille")
            self.assertEqual(str(cfg["fichier_ftnc"]).replace("\\", "/"), "C:/tmp/mon_planner.xlsx")
        finally:
            del os.environ["FTNC_FICHIER_PLANNER"]
            del os.environ["FTNC_FEUILLE_PLANNER"]

    def test_requirements_major_versions_are_pinned(self):
        """Vérifie que toutes les dépendances de requirements.txt ont une borne supérieure majeure."""
        req_path = Path(__file__).resolve().parents[1] / "requirements.txt"
        lines = [
            line.strip() for line in req_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertTrue(len(lines) > 0)
        for line in lines:
            with self.subTest(requirement=line):
                # Chaque paquet doit avoir une borne supérieure majeure (<X.0.0) ou un pin exact (==)
                self.assertTrue(
                    "<" in line or "==" in line,
                    f"La dépendance '{line}' n'a pas de borne de version supérieure !"
                )


if __name__ == "__main__":
    unittest.main()
