# Polymarket Bitcoin Prediction Bot

Bot automatisé qui trade sur les marchés de prédiction Bitcoin de Polymarket toutes les 15 minutes en utilisant l'analyse technique.

## Caractéristiques

- **Analyse technique multi-indicateurs**: RSI, MACD, EMA Crossover, Bollinger Bands
- **Système de scoring pondéré**: Combine les signaux pour des prédictions robustes
- **Paper trading**: Teste la stratégie sans risque avant le trading réel
- **Scheduler automatique**: Exécution toutes les 15 minutes alignée sur l'horloge
- **Logging détaillé**: Suivi complet des trades et de la performance

## Installation

### 1. Cloner et installer

```bash
cd /Users/moneyprinter/Documents/special-octo-umbrella
pip install -e ".[dev]"
```

### 2. Configuration

#### Option A: Mode Paper (Simulation) - RECOMMANDÉ POUR COMMENCER

```bash
# Copier le template
cp .env.example .env

# Éditer .env avec ces valeurs pour le paper trading:
POLYMARKET__PRIVATE_KEY=0x0000000000000000000000000000000000000000000000000000000000000001
POLYMARKET__FUNDER_ADDRESS=0x0000000000000000000000000000000000000000
POLYMARKET__SIGNATURE_TYPE=0

TRADING__MODE=paper
TRADING__TRADE_AMOUNT_USD=10.0
TRADING__INTERVAL_MINUTES=15
TRADING__MIN_SCORE_THRESHOLD=0.6
```

#### Option B: Mode Live (Trading réel)

**⚠️ NE PAS UTILISER AVANT D'AVOIR TESTÉ EN PAPER MODE**

1. **Créer/Obtenir un wallet Polygon:**

   Option 1 - Wallet existant (MetaMask):
   ```
   - Ouvrir MetaMask
   - Menu → Détails du compte → Exporter la clé privée
   - Copier la clé privée (0x...)
   - Copier l'adresse publique
   ```

   Option 2 - Nouveau wallet:
   ```bash
   pip install eth-account
   python scripts/create_wallet.py
   ```

2. **Obtenir des USDC sur Polygon:**
   - Bridge depuis Ethereum: https://wallet.polygon.technology/polygon/bridge
   - OU achète directement sur Binance/Kraken et retire sur Polygon

3. **Configurer .env pour le live:**
   ```bash
   POLYMARKET__PRIVATE_KEY=0xTON_PRIVATE_KEY_ICI
   POLYMARKET__FUNDER_ADDRESS=0xTON_ADRESSE_WALLET_ICI
   POLYMARKET__SIGNATURE_TYPE=0

   TRADING__MODE=live
   TRADING__TRADE_AMOUNT_USD=10.0
   ```

4. **Tester l'authentification:**
   ```bash
   python scripts/test_auth.py
   ```

## Utilisation

### Lancer le bot

```bash
# Mode interactif
python -m btc_bot

# Ou via le script d'entrée
btc-bot
```

### Lancer les tests

```bash
pytest tests/ -v
```

## Comment ça marche

### Cycle de trading (toutes les 15 minutes)

```
1. Fetch prix BTC (Binance)
   └─> Récupère 100 chandeliers 15min pour analyse

2. Calcul indicateurs techniques
   ├─> RSI (14): Détecte surachat/survente
   ├─> MACD (12,26,9): Identifie tendances et momentum
   ├─> EMA Crossover (9/21): Signaux de croisement
   └─> Bollinger Bands (20,2σ): Volatilité et extrêmes

3. Scoring multi-indicateurs
   ├─> Chaque indicateur vote: -2 (STRONG_SELL) à +2 (STRONG_BUY)
   ├─> Pondération: RSI 25%, MACD 30%, EMA 25%, BB 20%
   └─> Output: Direction (UP/DOWN) + Confidence (0-1)

4. Découverte marchés Polymarket
   └─> Filtre marchés Bitcoin actifs et liquides

5. Exécution trade
   ├─> Si confidence >= 60%: Trade
   ├─> Paper mode: Simulation locale
   └─> Live mode: Ordre market FOK sur Polymarket

6. Logging résultats
   └─> P&L, win rate, balance
```

### Exemple de signal

```
Signal: UP (confidence: 0.72)
Analysis: RSI(42.3): BUY | MACD: BUY | EMA: BUY | BB: NEUTRAL

→ Achète YES token (parie sur hausse BTC)
→ Montant: $10
→ Prix: 0.45 (45¢ par share)
```

## Structure du projet

```
polymarket-btc-bot/
├── src/btc_bot/
│   ├── main.py              # Orchestrateur principal
│   ├── config/
│   │   ├── settings.py      # Configuration Pydantic
│   │   └── constants.py     # Constantes et poids
│   ├── api/
│   │   ├── binance/         # Fetch données BTC
│   │   └── polymarket/      # Trading sur Polymarket
│   ├── analysis/
│   │   ├── indicators.py    # Calcul indicateurs
│   │   └── scoring.py       # Système de scoring
│   ├── trading/
│   │   ├── paper_trader.py  # Simulation
│   │   └── executor.py      # Exécution trades
│   └── scheduler/
│       └── job_scheduler.py # Scheduler 15 min
├── tests/                   # Tests unitaires
└── scripts/                 # Scripts utilitaires
```

## Configuration avancée

### Ajuster les indicateurs

Édite `config/settings.yaml`:

```yaml
indicators:
  # RSI
  rsi_period: 14
  rsi_overbought: 70.0
  rsi_oversold: 30.0

  # MACD
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9

  # EMA
  ema_short: 9
  ema_long: 21

  # Bollinger Bands
  bb_period: 20
  bb_std_dev: 2.0
```

### Modifier les poids des indicateurs

Dans `src/btc_bot/config/constants.py`:

```python
INDICATOR_WEIGHTS = {
    "rsi": 0.25,           # 25% du score total
    "macd": 0.30,          # 30%
    "ema_crossover": 0.25, # 25%
    "bollinger": 0.20,     # 20%
}
```

## Sécurité

🔒 **CRITIQUES:**

1. **JAMAIS** commit ta clé privée dans Git
2. Garde ton `.env` local uniquement
3. Commence TOUJOURS en paper mode
4. Utilise un wallet dédié avec montants limités
5. Active 2FA sur tous tes comptes exchange

## Performance

### Métriques suivies (Paper mode)

- **Total P&L**: Profit/perte total en USD et %
- **Win Rate**: % de trades gagnants
- **Trades exécutés**: Nombre total de positions
- **Balance courante**: Solde actuel du portefeuille

### Visualiser les résultats

```bash
# Le paper trader sauvegarde dans paper_trades.json
cat paper_trades.json | python -m json.tool
```

## FAQ

**Q: Pourquoi le bot ne trade pas à chaque cycle?**
- Le signal doit avoir une confiance >= 60%
- Le signal ne doit pas être NEUTRAL
- Il doit y avoir des marchés Bitcoin liquides disponibles

**Q: Comment améliorer la performance?**
- Backteste différents paramètres d'indicateurs
- Ajuste les poids du scoring
- Modifie le seuil de confiance minimum
- Teste sur plusieurs semaines en paper mode

**Q: Le bot peut perdre de l'argent?**
- OUI! C'est du trading, toujours un risque
- Utilise seulement l'argent que tu peux te permettre de perdre
- Commence avec de petits montants
- Surveille régulièrement les performances

**Q: Quel montant par trade?**
- Paper mode: N'importe quel montant pour tester
- Live mode: Commence avec $5-10 par trade
- Ajuste selon tes résultats et ton capital

## Support et développement

- **Issues**: Rapporte les bugs sur GitHub
- **Logs**: Vérifie les logs pour débugger
- **Tests**: Lance `pytest` avant de déployer des changements

## Avertissement

⚠️ **Ce bot est fourni à des fins éducatives. Le trading comporte des risques. Fais tes propres recherches et ne trade jamais plus que ce que tu peux te permettre de perdre.**

## Licence

MIT
