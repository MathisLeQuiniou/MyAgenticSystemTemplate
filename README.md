# MyAgenticSystemTemplate

Point de départ pour construire des systèmes agentiques avec **LangGraph** :
classes de base (agents, graphes, states, outils), API FastAPI, persistance
PostgreSQL, serveurs d'outils MCP et un frontend React pour **observer chaque
exécution** : chemin parcouru dans le graphe, appels LLM, appels d'outils,
tokens, durées, erreurs, en direct.

```
START → router ─research→ researcher [agent ⇄ tools] → writer → END
               └─direct──────────────────────────────→ writer
```

## Quick Start

### Prerequisites
Python ≥ 3.10, Node.js ≥ 20.19, Nginx >= 1.21.0, local PostgreSQL, a model supporting tool calling
with [Ollama](https://ollama.com) (for instance `ollama pull qwen3:8b`) - or any 
API openai compatible — or with the `fake` model to test without any LLM.

### Backend setup

```bash
python3.12 -m venv .venv
source activate .venv/bin/activate
pip install -r backend/requirements.txt
```

### Frontend setup

```bash
cd frontend
rm -rf node_modules package-lock.json dist
npm install
npm run build
```

### environement variables

```bash
cp .env.example .env
```
And fill-up all the environment variables

### Local Database initialization and/or migration

```bash
python -m backend.db.init_db
```

### Start the app

```bash
./app.sh
```

- Frontend : http://127.0.0.1:5173
- API (Swagger) : http://127.0.0.1:8000/docs

Dans le frontend, choisis le graphe, le modèle (`fake` fonctionne hors-ligne),
écris un message et lance. Le graphe s'anime en direct ; clique un nœud pour
filtrer la trace, clique une ligne de la trace pour voir prompts, réponses,
arguments et résultats d'outils.

Autres commandes : `./app.sh api | tools | front | migrate | test`.

## Structure

```
backend/
├── agentic/
│   ├── agents/        BaseAgent, LLMAgent (boucle outils en sous-graphe), RouterAgent
│   ├── graphs/        BaseGraph, graphs_registry (@register_graph), examples/
│   ├── states/        BaseState (TypedDict LangGraph) + reducers
│   ├── tools/         local_tools, tools_registry (ToolRegistry)
│   ├── llm/           profils de modèles + factory (OpenAI-compatible, Ollama, fake)
│   ├── skills/        SkillRegistry + outils load_skill / read_skill_file
│   └── tracing/       TraceCollector : astream_events LangGraph → événements de trace
├── tool_servers/      serveurs MCP (FastMCP) lancés par app.sh
├── api/               FastAPI : routes graphs / runs / SSE
├── config/            settings (.env), models.yaml, mcp_servers.yaml (+ loader mcp.py)
├── db/                modèles SQLAlchemy, repositories, Alembic
├── infra/             connexions externes : Postgres (sessionmaker), checkpointer LangGraph, client MCP
├── schemas/           modèles Pydantic (API + événements)
├── services/          RunService, EventBus (SSE)
├── prompts/           prompts système en Markdown (identité des agents)
├── skills/            skills au format SKILL.md (instructions chargées à la demande)
└── utils/
frontend/              React + TypeScript + Vite + React Flow
tests/
app.sh                 lanceur unique
```

## Concepts

### States — `backend/agentic/states`
`BaseState` est un `TypedDict` LangGraph avec `messages` (reducer `add_messages`)
et `context` (dict fusionné). Étends-le avec tes clés ; utilise les reducers
(`append_list`, `merge_dict`, `increment`) quand plusieurs nœuds écrivent la même clé.

### Agents — `backend/agentic/agents`
| Classe | Rôle |
|---|---|
| `BaseAgent` | Contrat minimal : `async run(state, config) -> update partiel`. `as_node()` le rend ajoutable au graphe. `get_model(config)` résout le modèle (override du run > profil de l'agent > défaut). `emit()` publie un événement custom dans la trace. |
| `LLMAgent` | Prompt système (`prompts/<nom>.md` ou texte) + outils. Avec outils, c'est un **sous-graphe** `agent ⇄ tools` : chaque appel d'outil devient une étape visible. `max_iterations` borne la boucle. Surcharge `format_prompt(state)` pour injecter du state. |
| `RouterAgent` | Demande au LLM de choisir une route, parse la réponse avec tolérance (repli sur `default`), écrit `state["route"]`. À brancher avec `add_conditional_edges(router.name, router.route, {...})`. |

### Graphes — `backend/agentic/graphs`
```python
@register_graph
class MyGraph(BaseGraph):
    name = "my_graph"
    description = "..."
    state_schema = MyState

    def build(self) -> StateGraph:
        agent = LLMAgent("assistant", prompt="assistant", tools=self.tools.get("calculate"))
        builder = StateGraph(self.state_schema)
        builder.add_node(agent.name, agent.as_node())
        builder.add_edge(START, agent.name)
        builder.add_edge(agent.name, END)
        return builder
```
Dépose le fichier n'importe où sous `backend/agentic/graphs/` : il est découvert
automatiquement, compilé avec le checkpointer Postgres, exposé par l'API et
dessiné par le frontend. Surcharge `build_input()` / `build_output()` si ton
graphe attend autre chose qu'un message.

### Outils — `backend/agentic/tools` et `backend/tool_servers`
- **Outils locaux** : fonctions `@tool` dans `tools/local_tools.py`.
- **Serveurs MCP** : déclarés dans `config/mcp_servers.yaml`. Ceux qui ont un
  `module` sont lancés par `app.sh` (exemple : `tool_servers/demo_server.py`,
  `calculate` + `search_knowledge_base`) ; les autres (externes, stdio…) sont
  seulement connectés. Un serveur indisponible est ignoré avec un warning.
- Dans un graphe : `self.tools.get("nom1", "nom2")` ou `self.tools.from_servers("demo")`.

### Skills — `backend/skills`
Une skill est un dossier au format Anthropic *Agent Skills* :
`<nom>/SKILL.md` (front matter `name` + `description`, puis les instructions)
et des fichiers annexes facultatifs (`references/`, `templates/`…).

```python
LLMAgent("researcher", prompt="researcher", tools=[...], skills=["financial-calculations"])  # ou ["*"]
```
L'agent reçoit dans son prompt système le **catalogue** (nom + description) et
deux outils : `load_skill(name)` pour lire les instructions, `read_skill_file(name, path)`
pour ouvrir une annexe (accès limité au dossier de la skill). Chaque chargement
apparaît dans la trace avec un badge **SKILL**. Liste via `GET /api/skills`.

**Prompt ou skill ?** Le prompt dit *qui* est l'agent et est toujours chargé ;
une skill dit *comment* faire une tâche précise, n'est chargée qu'au besoin et
peut être partagée entre agents. Ne recopie pas le contenu d'une skill dans un prompt.
Les scripts éventuels d'une skill ne sont pas exécutés : expose ce code comme outil
(local ou serveur MCP). Exemple fourni : `financial-calculations` (TVA, intérêts,
mensualités), branchée sur le `researcher`.

### LLM — `backend/config/models.yaml`
Un **profil** = un modèle joignable. Fournisseurs : `openai` (toute API
compatible OpenAI : OpenAI, passerelles internes, vLLM, Ollama `/v1`),
`ollama` (API native), `fake` (déterministe, pour tests/démo).

Pour l'**API interne sécurisée** de ton client, le profil `internal` prévoit :
`base_url`, clé via variable d'environnement, `default_headers`, `ca_bundle`
(CA d'entreprise), `verify_ssl`, `proxy`, `timeout`, `max_retries`. Les valeurs
`${VAR}` sont lues depuis l'environnement (`.env`).

Le profil par défaut se change dans `models.yaml` (`default:`) ou via
`DEFAULT_MODEL_PROFILE`, et chaque run peut en choisir un autre.

### Observabilité
`TraceCollector` filtre le flux `astream_events` de LangGraph pour ne garder que :
`node_*`, `llm_*` (messages, sortie, usage), `tool_*` (arguments, résultat),
`custom` et `llm_token` (live uniquement). Chaque événement porte un `node_path`
(`researcher:tools`) qui correspond aux ids de `BaseGraph.describe()`, et un
`parent_span_id` pour reconstruire l'arbre.

`RunService` exécute le graphe en tâche de fond, persiste les événements
(`app.events`) et les publie sur l'`EventBus` ; `GET /api/runs/{id}/stream`
rejoue l'historique puis diffuse en direct (SSE).

### Base de données
| Schéma | Contenu | Géré par |
|---|---|---|
| `app` | `runs`, `events` | SQLAlchemy + Alembic |
| `langgraph` | checkpoints (state par thread) | `AsyncPostgresSaver.setup()` |

Nouvelle migration après modification de `backend/db/models.py` :
```bash
.venv/bin/alembic -c backend/db/alembic.ini revision --autogenerate -m "ma modif"
./app.sh migrate
```

## API

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/health` | état DB, graphes, outils |
| GET | `/api/graphs` · `/api/graphs/{name}` | liste · structure (nœuds, arêtes, mermaid) |
| GET | `/api/models` | profils LLM |
| GET | `/api/skills` · `/api/skills/{name}` | skills disponibles · contenu |
| POST | `/api/runs` | `{graph, input: {message}, model_profile?, thread_id?}` |
| GET | `/api/runs` · `/api/runs/{id}` | liste · détail |
| GET | `/api/runs/{id}/events` | trace persistée |
| GET | `/api/runs/{id}/stream` | trace en SSE (replay + live) |
| GET | `/api/runs/{id}/state` | dernier état checkpointé du thread |
| POST | `/api/runs/{id}/cancel` | annule un run en cours |

Réutiliser un `thread_id` continue la conversation (historique restauré par le
checkpointer) ; le frontend le propose via « Continuer le thread du run affiché ».

## Pistes d'évolution
- Human-in-the-loop avec `interrupt()` de LangGraph + reprise via l'API.
- EventBus multi-process (Redis pub/sub ou Postgres LISTEN/NOTIFY) pour plusieurs workers.
- Export vers Langfuse / OpenTelemetry en plus de la trace maison.
- Authentification de l'API et du frontend.
