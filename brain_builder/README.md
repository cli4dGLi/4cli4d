# Brain Builder

Brain Builder is a colourful Streamlit learning app for young children. It includes mental maths, English and reading, Bible-story word problems, Creation Lab science/history, Wisdom Puzzles, progress tracking, a parent-only cognitive assessment centre, and a privacy-first voice reading assessment. The child-facing experience now uses original Bible-adventure companions inspired by David, Esther, Daniel, Ruth, Moses, and Miriam.

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

## Access control

Brain Builder requires a login before any page opens. The first admin account is bootstrapped from Streamlit secrets or environment variables, then the admin can create extra tablet users from the sidebar.

Create a password hash from inside the `brain_builder` folder:

```powershell
@'
from getpass import getpass
from utils.auth import hash_password
print(hash_password(getpass("Admin password: ")))
'@ | python -
```

Then set these secrets locally or in Streamlit Cloud:

```toml
BRAIN_BUILDER_ADMIN_USERNAME = "clifford"
BRAIN_BUILDER_ADMIN_PASSWORD_HASH = "pbkdf2_sha256$260000$..."
```

The app does not store or commit the plaintext password.

After signing in as admin, open the sidebar and use **Admin: users** to:

- create learner accounts for OB's tablet
- set or reset passwords
- make another grown-up an admin
- deactivate users who should no longer have access

## Child profiles

Several children can use the same app. After login, each child taps their name or adds a simple profile with:

- name
- age
- date of birth

Brain Builder uses the active child profile to separate scores, streaks, skill mastery, reading results, assessments, and daily learning plans. The age is used locally to tailor the development plan and daily exercises in real time. Child names and dates of birth are not sent to Claude for routine plan generation.

Parents can deliberately allow deeper Claude personalization inside **Grown-Up Tent > Parent settings**. When approved, Brain Builder may send the active child's name, age, and date of birth to Claude so generated questions, reading content, and development plans can be tailored more closely. This setting is off by default and can be turned off again at any time.

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

## Creation Lab topics

Creation Lab adds playful five-question sessions for:

- Natural Science
- Physics
- Geography
- Geometry
- Science Facts
- Science History
- World History

Each question includes a short read-aloud fact after the answer.

## Wisdom Puzzles

Wisdom Puzzles adds touch-friendly puzzle quests:

- Pattern Puzzles
- Odd One Out
- Memory Match
- Maze Rescue

Maze Rescue uses big arrow buttons to guide the learner through a grid maze.

## Daily Wisdom Journey Engine

Brain Builder includes a lightweight adaptive learning engine for daily progress:

- Tracks mastery for each skill after every completed session.
- Uses spaced repetition dates so weaker or due skills come back sooner.
- Builds a five-quest daily plan across maths, reading, word problems, science, and puzzles.
- Marks daily quests complete automatically when the child finishes the matching module and subtopic.
- Shows parents the lowest-mastery skills in **Growth Garden** so daily practice stays focused.

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
