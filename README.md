# SignalKit

**Field deployment intelligence for digital signage technicians.** SignalKit assigns pre-approved creative packages to installation sites using live Qloo geographic taste affinity. It does not generate content or require an LLM.

**Live demo:** https://signalkit-786561239973.us-central1.run.app

## Try it

Open the live demo and click **Analyze site fit**. The example has three approved packages, each anchored to a real artist, and screens in Chicago, Tulsa and Miami. You should see three different assignments. Chicago is flagged for human review because its two leading packages are close. Click **Approve deployment**, then download the technician CSV.

Edit any package name, artist, ID or screen format, or add sites from 105 supported US metros. Artists must match a Qloo entity exactly. A package with the wrong orientation cannot be assigned to a screen. Missing Qloo coverage never becomes a made-up recommendation.

## What Qloo does

For each package, the Anchor Scout calls `GET /search` to resolve the cultural anchor. The Geo Signal Analyst calls `GET /v2/insights` with `filter.type=urn:heatmap`, the Qloo entity ID and `filter.location.query=United States`. SignalKit reads each city's geohash cell and ranks its affinity among 105 US metros. The Deployment Arbiter picks the highest eligible package per site and flags weak or close signals. The Technician Gate requires approval before CSV export. The UI exposes the Qloo calls and the entire score matrix.

**No LLM is involved in selection.** Without Qloo's live city affinity signals, the assignment engine cannot make a data-backed selection. The percentiles measure relative cultural fit for each artist, **not** sales, foot traffic, or an absolute probability of liking the creative. Package assets are supplied and licensed by the user; SignalKit handles metadata and assignment only.

## Run locally

```bash
cp .env.example .env
# Set your QLOO_API_KEY in .env
uv sync
uv run uvicorn signalkit.main:app --reload
```

Then visit http://127.0.0.1:8000. Run the workflow checks with `uv run pytest -q`.

The Qloo API key stays server-side. Qloo responses are cached only in process memory and are not committed to this repository. Exported CSV files are generated after approval and downloaded to the technician's device. In-memory approval state expires when the service restarts.

## Stack

Python 3.12 · FastAPI · Qloo Taste AI · vanilla JavaScript/CSS · Google Cloud Run. Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com/). MIT licensed.
