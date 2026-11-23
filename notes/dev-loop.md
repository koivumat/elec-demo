# The development loop

Every step goes through the same loop. The agent builds a step on a branch
`step-NN-name` and opens a pull request (PR). You check out the branch, run it,
read the check report, merge and tag. Every PR description repeats these
commands with `NN-name` filled in.

You need two terminal windows, both in the project folder:

- **PY**: Anaconda Prompt (Windows `cmd` syntax)
- **GIT**: any terminal with git (Git Bash or cmd)

## The standard sequence

**1. Get the branch (GIT)**

```
git switch main
git pull
git switch step-NN-name
git pull
```

(The last `git pull` matters when the agent has pushed fixes to a branch you
already have.)

**2. Install, test, run (PY)**

```
conda activate elec
pip install -r requirements.txt
python -m pytest
python run_all.py
```

Steps that download data say so in their PR, and use `python run_all.py --fetch`
on the last line instead. Steps that change the paper or slides add `--latex`.

**3. Look at what changed (GIT)**

```
git status
git diff --stat
```

Then read the check report `checks/NN_name.md` (in your editor or on GitHub,
in the PR's "Files changed" tab). Compare EXPECT with SEE.

**4. Commit your verified outputs (GIT), only if step 3 listed changed files**

Changed files after a run are the results from your computer (downloaded
data, a report that now says your key was found). If they look right:

```
git add checks data results figures variants paper slides
git commit -m "Verified outputs from local run"
git push
```

If `git status` said "nothing to commit, working tree clean", skip this block.
If a file changed that you did not expect, stop and ask in the chat.

**5. Merge on GitHub**

Open the PR, click **Merge pull request** using **Create a merge commit**
(not squash), and confirm. Do not click "Delete branch" there; step 6 does it.

**6. Clean up and tag (GIT)**

```
git switch main
git pull
git branch -d step-NN-name
git push origin --delete step-NN-name
git tag verified-NN-name
git push origin verified-NN-name
```

The tag `verified-NN-name` marks a state you checked yourself. To go back to
it in a lecture: `git switch --detach verified-NN-name` (and `git switch main`
to return).

Small fixes between steps use a branch `fix-short-name` and the same loop,
without a tag.

## First-time setup (once per computer)

**GIT**: clone the project into the folder where you keep projects:

```
git clone https://github.com/koivumat/elec-demo.git
cd elec-demo
```

**PY**: go to the same folder (`cd` to it), then create the environment:

```
conda create -n elec python=3.13 -y
conda activate elec
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

In Notepad, replace `your-token-here` with your ENTSO-E token and save. (Or copy
an existing `.env` from another project into this folder.) The file `.env` is
never committed; git ignores it.

Then check everything with:

```
python run_all.py --steps 00
```

and read `checks/00_setup_check.md`. Every row should say OK.

### Without Anaconda: python.org and a .venv

Install Python 3.13 from python.org, then in a terminal in the project folder:

```
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS or Linux use `python3.13 -m venv .venv` and `source .venv/bin/activate`.
After that, the loop is the same, with `.venv\Scripts\activate` in place of
`conda activate elec`.
