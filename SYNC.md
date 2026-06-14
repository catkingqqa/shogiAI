# Local And Big-Data Host Sync

GitHub `main` is the shared source of truth. Runtime secrets, logs, PID files,
virtual environments, models, and import state remain excluded by `.gitignore`.

## Windows / Local

After changing code or adding game records:

```powershell
.\sync_repo.ps1 "Describe the local changes"
```

The script commits tracked content, rebases onto the latest GitHub `main`, and
pushes the result.

## Big-Data Host

The crawler writes live files to `~/climbbug`. After changing server code or
downloading new game records:

```bash
cd ~/shogiAI
./sync_remote.sh "Describe the remote changes"
```

The script copies crawler code, URL progress, and CSA files into the repository,
commits them, rebases onto GitHub `main`, pushes, and copies the merged result
back to `~/climbbug`.

## Receiving Changes

Run the relevant sync script on the other machine. If both machines modify the
same file, Git stops at the rebase conflict instead of overwriting either copy.
