# 🩺 MedAgent v2 — Offline AI Medical Data Assistant

Powered by **Ollama + llama3** locally. No data leaves your machine.

## Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install & start Ollama  (https://ollama.com)
ollama serve

# 3. Pull the LLM model
ollama pull llama3

# 4. Run the app
streamlit run app.py
```

## What's new in v2

| Area | Before | After |
|------|--------|-------|
| **Agent brain** | Returns `"Agent works"` | Full Ollama/llama3 integration with medical system prompt |
| **Data loader** | Reads only 1 sheet | Reads ALL sheets, auto-detects headers |
| **Tools** | Empty | Flag counts, diagnosis breakdown, age distribution |
| **UI** | Basic Streamlit defaults | Dark clinical theme, KPI cards, chat bubbles, suggestion chips |
| **Error handling** | None | Offline detection, timeout, clear messages |

## Usage

1. Open the app — `patients.xlsx` loads automatically from `data/`
2. Or upload any medical Excel file via the sidebar
3. Type a question in the chat or click a suggestion chip
4. MedAgent analyses the data and answers using medical knowledge

## Example questions

- *"Which patients have HbA1c above 6.5%?"*
- *"Show me PT-0001's complete profile"*
- *"What are the most common diagnoses?"*
- *"How many patients are on Metformin?"*
- *"List patients over 65 with hypertension"*
- *"Average cholesterol across all patients?"*

## Changing the model

Edit `agent.py` line 6:
```python
MODEL = "llama3"   # change to "mistral", "phi3", "gemma", etc.
```
