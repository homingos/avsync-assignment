# AV-Sync Offset Estimation — Assignment

In each video clip, the **audio has been shifted in time** relative to the video.
Your job: measure that shift, in milliseconds.

Some clips have a **constant** shift. Others **drift** — the shift changes over
the clip. You are not told which is which. Working that out is part of the task.

---

## 1. Get set up

```bash
git clone https://github.com/sunayana-moro/avsync-assignment.git
cd avsync-assignment
pip install -r requirements.txt
bash download_data.sh
```

You need `ffmpeg` on your PATH. Check with `ffmpeg -version`, and use
**Python 3.10-3.12** (mediapipe often has no wheel yet for the newest Python).
No GPU. No model training. Any laptop is fine.

After `download_data.sh` you will have:

```
data/dev/          40 clips + labels.json   <- answers included, to build against
data/heldout/      80 clips                 <- no answers, this is what we score
```

Every clip is **4.6 seconds** at 25 fps (115 frames), 512×512, with 16 kHz mono
audio. One person talking to camera, mouth visible throughout.

## 2. Build your method on the dev set

`data/dev/labels.json` has the true answer for every dev clip. Use it to check
whether your method works.

Score yourself any time:

```bash
python3 score.py --predictions my_dev_predictions.json --truth data/dev/labels.json
```

## 3. Answer format

One JSON file. A list. One entry per clip.

**Constant shift** — one number:

```json
{"clip_id": "clip_id_here", "type": "constant", "offset_ms": 12.4}
```

**Drifting shift** — a curve, as two lists of the same length:

```json
{"clip_id": "clip_id_here", "type": "drift",
 "t_s":       [0.0,  1.0,  2.0,  3.0,  4.0,  4.6],
 "offset_ms": [-5.0, 1.1,  7.2,  13.3, 19.4, 22.8]}
```

You choose the times in `t_s` and how many points to use. Values between your
points are interpolated; before the first and after the last, your end value is
held flat.

If you are confident the drift is a straight line, you may instead give just
two numbers — but note this commits you to estimating a *slope*, which is the
hardest part to get right:

```json
{"clip_id": "clip_id_here", "type": "drift", "start_ms": -5.0, "end_ms": 25.5}
```

**Sign convention:** positive `offset_ms` means the **audio comes later** than
the video. If a mouth closes at 1.000s and you hear the sound at 1.020s, the
offset is **+20 ms**.

See `example_submission.json` for a complete valid file.

## 4. Submit

Submitting is done with a pull request, so basic Git and GitHub skills are part
of what we are looking at.

1. **Fork** this repository (button, top right).
2. Clone your fork and make a branch:
   ```bash
   git checkout -b submission/YOUR_GITHUB_USERNAME
   ```
3. Create a folder named **exactly** as your GitHub username, with three
   things in it:
   ```
   submissions/YOUR_GITHUB_USERNAME/
     predictions.json     your answers for data/heldout/
     run.py               (or run.sh) regenerates predictions.json from the clips
     METHOD.md            1-2 pages: what you did and why
   ```
   The folder name has to match your username, or the check will reject it.

4. **Encrypt it.** One command:
   ```bash
   python3 tools/encrypt_submission.py submissions/YOUR_GITHUB_USERNAME
   ```
   This checks your predictions are valid, then packs the folder into a single
   encrypted `submission.enc`.

   Why: pull requests on a public repository are readable by **anyone**, with
   no login. Without this, every candidate could read your answers and your
   code, and you could read theirs. Encrypting means only we can open it.

   The script refuses to package an invalid submission, so **this is where you
   find out about format problems** — fix them and run it again.

5. Commit **only the encrypted file** and push:
   ```bash
   git add submissions/YOUR_GITHUB_USERNAME/submission.enc
   git commit -m "Submission: YOUR_GITHUB_USERNAME"
   git push origin submission/YOUR_GITHUB_USERNAME
   ```
   Keep your `predictions.json`, `run.py` and `METHOD.md` on your own machine.
   `.gitignore` already stops them being committed by accident, and the check
   rejects them if they slip through — both to protect your work.

6. Open a **pull request** against this repository's `main`.

**Do not commit the video files or the `data/` folder.** `.gitignore` already
excludes them. A PR containing clips will be closed.

### What happens when you open the PR

A check runs automatically within a minute or two. Because your submission is
encrypted, it verifies the **shape** of what you sent: your folder is named
after you, it holds exactly one `submission.enc`, and that file is a
well-formed sealed bundle.

The content check — valid JSON, every held-out clip present, no unknown ids,
sane numbers — already ran on your machine in step 4, because that is the only
place the plaintext exists.

It does **not** tell you your score. A green check means your submission can be
opened and read, not that it is accurate.

If the check fails, read the comment, push a fix to the same branch, and the
check runs again. Iterating until it is green is expected and costs you nothing
— pushes to your branch are not graded, only the merge is.

**You get up to 3 graded submissions.** Once your PR is merged it is scored; if
you later want to revise, open another PR and it is scored again, up to three
times total. This is not there to rush you — it is there because a score that
can be queried without limit can be worked backwards. Getting the format green
costs you none of the three.

## 5. How you are scored

- **Constant clip:** average gap between your answer and the truth, sampled over
  the clip, in milliseconds. If you answer with a single number this is just
  `|your answer − truth|`; if you answer with a curve, we average it over the
  clip rather than reading it at one instant.
- **Drifting clip:** the same thing — average gap between your curve and the
  true curve, sampled over the clip.

**Your score is your p80 error: the error your worst 20% of clips stay under.
Lower is better.** That is what the leaderboard ranks on.

We use p80 rather than the average on purpose. A method can post a good average
by nailing the easy clips and failing badly on the hard ones, and the average
hides that. p80 asks a different question: how bad does your method get when
the clip is difficult? We would rather see a method that is decent everywhere
than one that is excellent on half the set and lost on the rest.

Two consequences worth planning for:

- A single clip you get very wrong costs you little on the average but can move
  your p80. Handling awkward clips gracefully is worth more than squeezing the
  last millisecond out of the easy ones.
- You do not need to guess a clip's type correctly to score well. A constant
  clip answered with a gently sloping curve is scored on the average gap, so a
  wrong call about the type costs you only the gap it actually creates.

**What you get back is your p80 and nothing else.** Not your mean, not a
per-clip breakdown, not which clips you got wrong. You have the full picture on
the dev set, where the answers are already yours — use it.

We do look at your mean, your p90 and your error split by clip type on our
side, when we read your `METHOD.md`.

**Your score is published publicly.** This is a public repository, so the
grading run's output is visible to anyone: your GitHub username and your p80
appear in a leaderboard on the Actions run page. Your per-clip results are
not published, and neither is anyone else's. If you would rather your score
were not public, say so before you submit and we will grade you privately
instead — it makes no difference to how you are assessed.

**Roughly what to aim for.** So you know when to stop rather than burning a
weekend: on our own reference implementations, a single global
cross-correlation with no sub-frame refinement scores about **27 ms p80**, and
our best implementation scores about **22 ms p80**. If you land in that
neighbourhood you are doing fine. The gap between a crude method and a careful
one is genuinely a few milliseconds here, so do not read a small number as
failure.

## 6. Rules

- Use whatever libraries you like, so long as it runs on CPU in minutes.
- **AI tools are welcome.** We care that you can explain and defend every choice
  in `METHOD.md`, not that you typed it yourself.
- Do not try to obtain the held-out answers. They are not in this repository.
- Spend about **3–5 hours**. A simple method you fully understand beats a
  complicated one you cannot explain.

## 7. Hints

- Two signals to line up: something about **mouth movement** per video frame,
  and something about **loudness or emphasis** per audio frame. Cross-correlate
  them and the peak tells you the offset.
- At 25 fps, one frame is **40 ms**. Many answers are *between* frames, so a
  whole-frame answer cannot be right. You need sub-frame precision — look up
  interpolating the peak of a correlation function.
- For drifting clips, one number for the whole clip is wrong by construction.
  Think about measuring in short windows across the clip.
- Short windows are noisy; long windows blur the drift. That tradeoff is worth
  writing about in `METHOD.md`.

Questions: open an issue.
