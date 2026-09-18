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

## Analytics contract rollout

The frontend supports ratings, detailed negative feedback and suggestions. The
analytics endpoints are resolved from `DOCTOOME_ANALYTICS_API_BASE_URL`:

- `POST /analytics/ratings`
- `POST /analytics/feedback`
- `POST /analytics/suggestions`

The current backend rejects unknown `/chat` fields, so the extended request
contract is disabled by default:

```sh
export CHAT_EXTENDED_CONTRACT_ENABLED=false
```

With the flag disabled, `/chat` continues to receive only `message` and the
optional existing `conversation_id`. The frontend still creates and stores a
`user_message_id`, but does not send it.

After the backend accepts `user_message_id` and nullable `user_id`, enable:

```sh
export CHAT_EXTENDED_CONTRACT_ENABLED=true
```

The client accepts both legacy responses and future responses containing
`turn_id` and `assistant_message_id`. Rating and detailed-feedback controls are
only active for responses carrying a backend-provided `assistant_message_id`;
the frontend never fabricates one. Suggestions remain available without an
assistant message ID.

Recommended rollout:

1. Deploy the frontend with the extended contract disabled.
2. Deploy and verify the backend fields and analytics endpoints.
3. Enable the extended contract in the frontend environment.
4. Verify returned analytics IDs and feedback submissions.

For Streamlit Community Cloud, root-level entries in the app's Secrets settings
are exposed as environment variables:

```toml
DOCTOOME_CHAT_API_URL = "https://wp3xsfphbp.eu-west-3.awsapprunner.com/chat"
DOCTOOME_ANALYTICS_API_BASE_URL = "https://wp3xsfphbp.eu-west-3.awsapprunner.com"
CHAT_EXTENDED_CONTRACT_ENABLED = "false"
```

No AWS, OpenAI or Doctoome API credentials belong in this frontend. The EN/FR
selector controls frontend analytics text only; it does not alter chatbot
messages or `/chat` payload language.

## Verify

```sh
pip install -r requirements-dev.txt
python -m pytest -q -p no:cacheprovider
ruff check .
python -m compileall -q frontend_api.py frontend_state.py localization.py streamlit_app.py tests
```
