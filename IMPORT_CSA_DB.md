# Import CSA Games Into MySQL

This script imports CSA game records into the database tables:

- `users`
- `players`
- `game_records`
- `moves`
- `positions`

## Install Dependency

```powershell
python -m pip install -r requirements.txt
```

## Dry Run

Check how many games, moves, and positions would be imported:

```powershell
python src\import_csa_to_db.py --input data\game1.csa --dry-run
```

## Import One CSA File

```powershell
python src\import_csa_to_db.py ^
  --input data\game1.csa ^
  --host 140.135.65.53 ^
  --port 3306 ^
  --user 11211213 ^
  --database DB11211213 ^
  --skip-existing
```

The script asks for the MySQL password if `--password` is not supplied.

## Import Every CSA File In `data`

```powershell
python src\import_csa_to_db.py ^
  --input data ^
  --recursive ^
  --host 140.135.65.53 ^
  --port 3306 ^
  --user 11211213 ^
  --database DB11211213 ^
  --skip-existing
```

## Import In Smaller Batches

Some school MySQL accounts have a query limit such as `max_questions = 6000`.
Use `--max-games` to import fewer games per run:

```powershell
python src\import_csa_to_db.py ^
  --input data ^
  --recursive ^
  --host 140.135.65.53 ^
  --port 3306 ^
  --user 11211213 ^
  --database DB11211213 ^
  --skip-existing ^
  --max-games 20
```

Run the same command again later. `--skip-existing` skips games that are already
in `game_records.original_file_name`.

## Create Tables Automatically

If the five tables do not exist yet, add `--create-tables`:

```powershell
python src\import_csa_to_db.py --input data --recursive --create-tables --host 140.135.65.53 --user 11211213 --database DB11211213
```

## Password From Environment

To avoid typing the password every time:

```powershell
$env:MYSQL_PASSWORD="your-password"
python src\import_csa_to_db.py --input data --recursive --host 140.135.65.53 --user 11211213 --database DB11211213 --skip-existing
```
