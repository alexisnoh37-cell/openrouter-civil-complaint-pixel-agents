# OpenRouter Civil Complaint Pixel Agents

Pixel Agents office customized to visualize a Korean public-service complaint workflow powered by OpenRouter.

Upload a complaint file and watch seven agents move through classification, jurisdiction review, similar-case search, drafting, expression review, missing-question review, and privacy review in real time.

## Features

- Pixel-art visualization for seven complaint-processing agents
- OpenRouter calls through a FastAPI backend
- Real-time agent status updates using Server-Sent Events
- Complaint upload support for TXT, Markdown, CSV, XLSX, and XLS
- TF-IDF similar-case search with a safe empty result when data is unavailable
- API keys remain server-side and are excluded from Git

## Requirements

- Node.js 20 or later
- Python 3.11 or later
- An OpenRouter API key

## Setup

Open PowerShell in the repository directory:

```powershell
.\setup.ps1
```

Then create `civil-backend/.env` from `.env.example`:

```dotenv
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
```

## Run

```powershell
.\start-openrouter-office.ps1
```

Open `http://127.0.0.1:3100`, upload a complaint file, and select **분석 및 초안 생성**.

Stop both services with:

```powershell
.\stop-openrouter-office.ps1
```

## Architecture

- `webview-ui/`: Pixel Agents office and complaint upload panel
- `server/`: standalone Pixel Agents server using the OpenRouter provider
- `civil-backend/`: FastAPI, OpenRouter orchestration, SSE, privacy checks, and TF-IDF search
- `README.pixel-agents.md`: original Pixel Agents documentation

## Security

Never commit `civil-backend/.env`. Only `.env.example` belongs in Git. Real complaint files may contain personal information and should not be committed.

## Attribution

Based on [Pixel Agents](https://github.com/pixel-agents-hq/pixel-agents), licensed under the MIT License. The original license and notices are retained.
