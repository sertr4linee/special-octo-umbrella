#!/usr/bin/env python3
"""Script pour tester l'authentification Polymarket."""

import sys
from pathlib import Path

# Ajouter le src au path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from btc_bot.config.settings import get_settings
from btc_bot.api.polymarket.auth import PolymarketAuth


def test_auth():
    """Teste la connexion à Polymarket."""
    print("=" * 70)
    print("TEST D'AUTHENTIFICATION POLYMARKET")
    print("=" * 70)

    try:
        # Charger la config
        settings = get_settings()
        print(f"\n✓ Configuration chargée")
        print(f"  Mode: {settings.trading.mode.value}")
        print(f"  Funder: {settings.polymarket.funder_address[:16]}...")

        # Tester l'authentification
        print(f"\n⏳ Test de connexion...")
        auth = PolymarketAuth(settings.polymarket)

        # Connexion read-only (pas besoin de credentials)
        readonly_client = auth.get_readonly_client()
        print(f"✓ Client read-only créé")

        # Si on a des credentials, tester l'auth complète
        if settings.polymarket.private_key.get_secret_value():
            print(f"\n⏳ Test d'authentification L1/L2...")
            try:
                authenticated_client = auth.get_authenticated_client()
                print(f"✓ Authentification réussie!")
                print(f"  API credentials dérivées")

                # Tester une requête simple
                # orders = authenticated_client.get_orders()
                # print(f"✓ Requête API réussie ({len(orders)} ordres ouverts)")

            except Exception as e:
                print(f"✗ Échec authentification: {e}")
                print(f"\nVérifie que:")
                print(f"  1. Ta clé privée est correcte")
                print(f"  2. L'adresse funder correspond au wallet")
                print(f"  3. Le signature_type est correct (0 pour EOA)")
                return False
        else:
            print(f"\n⚠️  Pas de clé privée configurée")
            print(f"  Mode paper: OK")
            print(f"  Mode live: Configure POLYMARKET__PRIVATE_KEY dans .env")

        print(f"\n{'=' * 70}")
        print("✓ TEST RÉUSSI")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_auth()
    sys.exit(0 if success else 1)
