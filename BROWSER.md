# CSA Browser

This project includes a small CSA game browser with a Python standard-library API.

## Run

```powershell
python src\csa_browser_api.py --host 127.0.0.1 --port 8000
```

If Windows only exposes the Python launcher:

```powershell
py src\csa_browser_api.py --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

## API

```text
GET /api/games
GET /api/games/<game-id>?ply=<number>
```

CSA files are loaded from the `data` directory. `ply=0` is the initial position,
and each later ply is the board after that many moves.
