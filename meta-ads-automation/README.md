# Meta Ads Automation — Setup replicável

Setup local que replica o que o anúncio "Tráfego Pago Automatizado com Claude Code" promete:

- **MCP server** (Meta Marketing API) para o Claude Code operar sua conta de anúncios
- **Coletor de insights** que roda 3x/dia via cron e guarda em SQLite
- **Engine de regras** que classifica cada anúncio em `ESCALAR / MANTER / MATAR`
- **Dashboard local** (Streamlit) para visualizar CPA, CTR, CPM e a recomendação

Não é curso, não é caixa-preta — é código auditável em Python.

---

## Pré-requisitos

1. **Meta Business account** com acesso à Marketing API.
2. **System User token** de longa duração (System Users → Generate Token → escopos: `ads_read`, `ads_management`, `business_management`).
3. **Ad Account ID** (`act_XXXXXXX`).
4. Python 3.10+.

## Instalação

```bash
cd meta-ads-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edita o .env com o teu token + ad account id
```

Inicializa o banco:

```bash
python -m collector.fetch_insights --init
```

## Uso

### 1. Coletor (roda 3x/dia)

Puxa insights dos últimos 7d para todos os anúncios ativos:

```bash
python -m collector.fetch_insights
```

Agenda no cron (exemplo: 08:00, 14:00, 20:00 hora local):

```
0 8,14,20 * * * cd /caminho/meta-ads-automation && .venv/bin/python -m collector.fetch_insights >> data/collector.log 2>&1
```

### 2. Engine de regras

Aplica ESCALAR / MANTER / MATAR baseado nos thresholds em `rules/config.yaml`:

```bash
python -m rules.engine
```

### 3. Dashboard

```bash
streamlit run dashboard/app.py
```

Abre em `http://localhost:8501`.

### 4. MCP server (opcional — para o Claude Code operar a conta)

Adiciona ao `~/.claude.json` (ou `settings.json` do projeto):

```json
{
  "mcpServers": {
    "meta-ads": {
      "command": "python",
      "args": ["-m", "mcp_server.meta_ads_mcp"],
      "cwd": "/caminho/absoluto/meta-ads-automation",
      "env": {
        "META_ACCESS_TOKEN": "seu_token",
        "META_AD_ACCOUNT_ID": "act_XXXXXXX"
      }
    }
  }
}
```

Ferramentas expostas: `list_campaigns`, `list_ads`, `get_insights`, `pause_ad`, `resume_ad`, `update_daily_budget`.

## Regras (thresholds default)

Edite `rules/config.yaml`:

| Sinal | ESCALAR | MANTER | MATAR |
|---|---|---|---|
| ROAS (7d) | ≥ 2.5 | 1.2 – 2.5 | < 1.0 |
| CPA vs meta | ≤ 80% | 80–120% | > 150% |
| CTR (link) | ≥ 1.5% | 0.8–1.5% | < 0.5% |
| Frequência (7d) | < 2.5 | 2.5–3.5 | > 4.0 |
| Spend mínimo p/ julgar | R$ 50 acumulado | | |

Anúncios com spend < mínimo ficam como `APRENDENDO`.

## CAPI / Conversions API

Este setup **lê** dados. Para **enviar** eventos server-side (CAPI), veja `capi/README.md` (stub — próxima iteração). Documentação oficial da Meta cobre 100% do fluxo: <https://developers.facebook.com/docs/marketing-api/conversions-api>.

## Aviso

Você é responsável pelas ações executadas na sua conta de anúncios. Comece com `--dry-run` no engine de regras antes de dar autonomia de escrita.
