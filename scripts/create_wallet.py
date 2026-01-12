#!/usr/bin/env python3
"""Script pour créer un nouveau wallet Polygon pour Polymarket."""

from eth_account import Account

# Activer les fonctionnalités non audités (pour la génération de clés)
Account.enable_unaudited_hdwallet_features()

def create_wallet():
    """Crée un nouveau wallet et affiche les détails."""
    # Générer un nouveau compte
    account = Account.create()

    print("=" * 70)
    print("NOUVEAU WALLET CRÉÉ")
    print("=" * 70)
    print(f"\n⚠️  IMPORTANT: Sauvegarde ces informations en sécurité!\n")
    print(f"Adresse (Funder Address):")
    print(f"  {account.address}")
    print(f"\nClé privée (Private Key):")
    print(f"  {account.key.hex()}")
    print(f"\n{'=' * 70}")
    print("\nPROCHAINES ÉTAPES:")
    print("1. Copie ces informations dans ton fichier .env")
    print("2. Envoie des USDC sur l'adresse Polygon ci-dessus")
    print("3. GARDE LA CLÉ PRIVÉE SECRÈTE - ne la partage JAMAIS")
    print("=" * 70)


if __name__ == "__main__":
    create_wallet()
