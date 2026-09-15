# Doctoome chatbot testing frontend

Small Streamlit client for the deployed Doctoome practitioner-search chatbot.
The backend remains responsible for intent parsing, search, conversation state,
selection validation and URL construction.

## Run

Use Python 3.12:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export DOCTOOME_CHAT_API_URL="https://wp3xsfphbp.eu-west-3.awsapprunner.com/chat"
streamlit run streamlit_app.py
```

To test against a local API instead:

```sh
export DOCTOOME_CHAT_API_URL="http://localhost:8000/chat"
streamlit run streamlit_app.py
```

The client stores the opaque `conversation_id` returned by the backend in
Streamlit session state and sends it with every later message. Starting a new
conversation clears that ID and the display history without calling the API.

## Verify

```sh
pip install -r requirements-dev.txt
python -m pytest -q -p no:cacheprovider
ruff check .
python -m compileall -q frontend_api.py streamlit_app.py tests
```
