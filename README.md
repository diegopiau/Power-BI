# Diário do Bernardo

App **single-file HTML** para acompanhamento diário do Bernardo (prematuro tardio, 35s+3d).
Mobile-first, funciona offline após primeira visita e instala-se como PWA no telemóvel.

## Ficheiro

O app inteiro está em [`index.html`](./index.html) — HTML + Tailwind (CDN) + Alpine.js (CDN) + Chart.js (CDN),
persistência em `localStorage`, manifest e service worker inline (data URI / Blob).
**Não precisa de build.**

## Como usar

### Localmente (uso pessoal rápido)
Abrir `index.html` diretamente no browser. Funciona, mas o service worker pode não registar em `file://`.
Para PWA/offline recomenda-se servir por HTTP:

```bash
# opção 1: python
python3 -m http.server 8080
# opção 2: npx
npx serve .
```

Depois abrir `http://localhost:8080` no browser.

### Instalar no telemóvel (PWA)

**iPhone (Safari):** abrir a URL → Partilhar → **"Adicionar ao ecrã principal"**.
**Android (Chrome):** abrir a URL → menu ⋮ → **"Instalar app"** (ou "Adicionar ao ecrã principal").

Depois de instalado, funciona **100% offline** e abre em ecrã inteiro como uma app nativa.

## Deploy grátis (recomendado)

### GitHub Pages
1. Push do repo para GitHub.
2. Repo → **Settings → Pages → Source: `main` branch, `/` (root)**.
3. Após 1–2 min, o app fica em `https://<utilizador>.github.io/<repo>/`.

### Netlify
1. Arrastar a pasta para [app.netlify.com/drop](https://app.netlify.com/drop).
2. URL pública imediata; ligar a repo para redeploy automático.

### Cloudflare Pages / Vercel
Criar projeto a partir do repo, sem configuração de build (é HTML estático).

## Estrutura de dados (`localStorage`)

| Chave | Conteúdo |
|-------|---------|
| `bernardo_profile`  | perfil do bebé (nome, DN, idade gestacional, peso ao nascer, flag Hashimoto) |
| `bernardo_settings` | metas configuráveis (mamadas/dia, mínimo fraldas, ganho g/dia, ml/kg/dia, refeições) |
| `bernardo_records`  | array de eventos `{ id, type, timestamp, data }` |
| `bernardo_theme`    | `'light'` \| `'dark'` |
| `bernardo_timer`    | `{ startedAt }` — timer de mamada persistente entre sessões |

Tipos de evento (`type`): `feeding`, `diaper`, `weight`, `pumping`, `promil`, `colic`, `note`.
A documentação completa dos campos por tipo está no comentário no topo do `index.html`.

## Funcionalidades

- **Hoje**: KPIs com cores (verde/amarelo/vermelho), alertas ativos, 2 botões gigantes (mamada / fralda),
  suplemento sugerido em ml/refeição, timeline dos últimos registos.
- **Gráficos**: peso com linha de meta +Xg/dia, mamadas/dia, fraldas (stacked), suplemento/dia,
  heatmap de mamadas por hora × dia. Filtros 7/14/30 dias. Botão **CSV semana atual**.
- **Histórico**: agrupado por dia, filtros por tipo, tap para editar, apagar com **undo**.
- **Guia**:
  - *Idade Corrigida* — expectativas de sono/mamadas/marcos e fase de cólicas adaptadas à idade corrigida do momento.
  - *Consulta* — cards colapsáveis com pega, sinais de fome, sucção, técnica biberão, massagem da conchinha,
    power pumping, aviso ⚠️ **sem iodo** (Hashimoto), calculadora de suplemento integrada.
- **Timer de mamada** integrado (start/stop, persiste em background).
- **Alertas inteligentes**: ganho de peso baixo, fraldas insuficientes, intervalo >4h, suplemento a subir/descer semana a semana.
- **Backup**: exportar/restaurar JSON, apagar tudo (confirmação dupla).
- **Dark mode** legível de madrugada (cinza escuro, não preto puro).

## Aviso

Este app é uma ferramenta de registo pessoal. **Não substitui** acompanhamento médico ou de enfermagem.
Em caso de dúvida ou sinal de alerta, contactar a **Enfª Daniela Felizardo**, o pediatra do Bernardo ou o
**SNS 24 (808 24 24 24)**.
