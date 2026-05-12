# CSA Browser

This project includes a small CSA game browser with a Python API. The browser can
read games from MySQL or directly from local CSA files.

## Run

```powershell
python src\csa_browser_api.py --host 127.0.0.1 --port 8000 --source mysql --db-host 140.135.65.53 --db-port 3306 --db-user 11211213 --db-name DB11211213
```

If Windows only exposes the Python launcher:

```powershell
py src\csa_browser_api.py --host 127.0.0.1 --port 8000 --source mysql --db-host 140.135.65.53 --db-port 3306 --db-user 11211213 --db-name DB11211213
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

With `--source mysql`, games are loaded from `game_records`, `moves`, and
`positions`. `ply=0` is the initial position, and each later ply is the board
after that many moves.

To use local CSA files instead of MySQL:

```powershell
python src\csa_browser_api.py --source csa --host 127.0.0.1 --port 8000
```
