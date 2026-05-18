# Brain Builder

Brain Builder is a colourful Streamlit learning app for OB, age 5 years 3 months. It includes mental maths, English and reading, story word problems, Wonder Lab science/history, progress tracking, a parent-only cognitive assessment centre, and a privacy-first voice reading assessment. The child-facing experience uses original Hero Academy and Rescue Pup-style mascots, without copyrighted characters or logos.

## Run locally

From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

On macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Anthropic API key

The app never hardcodes the API key. Use either an environment variable:

```powershell
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"
streamlit run app.py
```

Or create `.streamlit/secrets.toml`:

```toml
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

If no key is set, Brain Builder uses the local fallback content in `assets/fallback_content.json`, so every module remains playable.

## Wonder Lab topics

Wonder Lab adds playful five-question sessions for:

- Natural Science
- Physics
- Geography
- Geometry
- Science Facts
- Science History
- World History

Each question includes a short read-aloud fact after the answer.

## Deploy to Streamlit Cloud

1. Push the `brain_builder` folder to a GitHub repository.
2. Go to [streamlit.io/cloud](https://streamlit.io/cloud).
3. Create a new app from your GitHub repo.
4. Set the main file path to `brain_builder/app.py` if the folder is inside a larger repo, or `app.py` if this folder is the repo root.
5. In Streamlit Cloud app settings, open **Secrets** and add:

```toml
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

6. Deploy.

## Parent PIN

The default parent PIN is `1234`. You can change it inside **OB's Assessment Centre > Parent settings**.

## Privacy for voice reading

Voice reading uses the browser Web Speech API. The microphone starts only after a button press, shows a green listening indicator, and stops after speech ends or the Done button is pressed. No audio is saved to disk, stored in SQLite, or sent to any API. Only the text transcript is analysed.

## Data

SQLite data is stored in `brain_builder.db`, which is created automatically on first run. Parents can export the full history as CSV from the dashboards.
