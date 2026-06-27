# AIAgent — Offline Medical Data Assistant

A fully offline AI agent for querying and analysing medical patient databases. Built with Python, Streamlit, and Ollama (llama3) — no data ever leaves your machine.

## What it does

Upload a medical Excel database and ask questions in plain English. The agent uses a local LLM to generate a query plan, executes it against the data with pandas, and returns results as interactive tables.

## Tech Stack

- **UI:** Streamlit
- **AI:** Ollama (llama3) — runs fully offline
- **Data:** pandas + openpyxl
- **Language:** Python

## Features

- Natural language queries over Excel patient databases
- Automatic sheet detection and cross-sheet joins
- Fuzzy string matching for flexible filtering
- KPI dashboard — total patients, average age, abnormal lab flags
- Suggestion chips for common queries
- Fully offline — no API calls, no data sharing
- Dark clinical UI theme

## Project Structure

```plaintext
offline-med-agent/
├── app.py           # Streamlit UI
├── agent.py         # Ollama integration and query execution
├── tools.py         # Analytics utilities (flags, diagnoses, age distribution)
├── data_loader.py   # Excel parsing
├── data/
│   └── patients.xlsx
└── requirements.txt
```

## Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running

### Setup

```bash
git clone https://github.com/SorenUPP/AIAgent.git
cd AIAgent/offline-med-agent
pip install -r requirements.txt
```

### Run Ollama

```bash
ollama serve
ollama pull llama3
```

### Run the app

```bash
streamlit run app.py
```

Then open `http://localhost:8501` and upload your Excel file or use the default `patients.xlsx`.

## Example Queries

- "How many patients have diabetes?"
- "Show me all patients over 70 with abnormal cholesterol"
- "Which patients have a penicillin allergy?"
- "What is the average BMI?"

## License

MIT
