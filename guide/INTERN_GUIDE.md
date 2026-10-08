# CT Anatomy Explorer v0.5 – 4-day plan (8–14 October 2026)

**Goal for Wednesday 14 October:** a public web link where anyone can open 5 real CT scans, see 12 organs outlined
by the VISTA-3D AI model next to the expert outlines, switch to a comparison view, read the Dice and volume
numbers, and download the masks. Plus a GitHub release, a 2–3 minute demo video and a faculty review.

Working days: **Thu 8 Oct**, (break Fri 9 – Sun 11), **Mon 12**, **Tue 13**, **Wed 14**.

| Who | Role |
|---|---|
| **Intern A** | AI pipeline on Kaggle: data, VISTA-3D, scores, export |
| **Intern B** | Website on GitHub Pages: viewer, polish, testing |
| **DrRB** | Daily review, faculty contact, decisions |

**Every day:** 10-minute stand-up at 9:30 (done · doing · blocked). By 5:30 pm post the day's proof
(a link or a screenshot) in the group chat. DrRB approves or redirects.

**Golden rules:** public data only – never put real patient scans on Kaggle, Colab, GitHub or a rented GPU.
Every page and slide says "Educational use only. Not for diagnosis."

---

## Day 1 – Thursday 8 Oct · "First AI mask on screen"

**Morning (both, with DrRB):** read this guide and the README; agree who owns what.

### Intern A – Kaggle
- [ ] Kaggle account with **phone verified** (needed for GPU and Internet).
- [ ] *Create → New Notebook → File → Import Notebook* → upload `notebooks/ct_anatomy_explorer_kaggle.ipynb`.
- [ ] *Session options:* Accelerator **GPU T4 x2** (or P100), Internet **On**.
- [ ] Keep `N_CASES = 1`. Run Steps 0–6 one by one. Step 1 downloads 3.2 GB (5–10 min).
- [ ] Write down from Step 4: **seconds per scan** and **peak GPU memory (MB)**.
- [ ] Step 6 picture: liver on the *left* of the axial image (that is the patient's right); AI and expert masks
      should look alike. Any line starting with **!** in Step 5 → stop and tell DrRB.
- [ ] Study `pipeline/organs.py` and `pipeline/evaluate.py`. Be ready to explain Dice in one sentence.
- [ ] **Before leaving (by 5 pm):** set `N_CASES = 10`, click **Save Version → Save & Run All (Commit) → Save**.
      Check that the new version shows "Running". It finishes on its own over the break.

### Intern B – GitHub Pages
- [ ] Create a **public** repository `ct-anatomy-explorer` (DSU organisation if there is one; add Intern A and DrRB).
- [ ] Upload the whole starter kit: *Add file → Upload files* → drag in all folders → *Commit*.
      (Web upload allows files up to 25 MB, which is enough here.)
- [ ] *Settings → Pages →* Deploy from a branch → `main` / `/docs` → Save. Wait 1–2 minutes.
- [ ] Open the site on a laptop **and** a phone. The demo case must load, and Expert / AI / Compare must switch.
- [ ] First edit: in `docs/index.html` replace `Built by the DSU AI Factory interns` with your names, and commit it.
- [ ] Read `docs/app.js` (start with `loadCase`, `applyLayers`, `computeCompare`, `onLocation`).
- [ ] Log anything odd as a GitHub *Issue*.

**Proof by 5:30 pm:** A posts the Step 6 picture + time + GPU memory and confirms the background run started.
B posts the live link.

---

## Fri 9 – Sun 11 · Break
Nothing to do. Kaggle runs the 10 scans in the background.

---

## Day 2 – Monday 12 Oct · "Real scans live"

### Intern A
- [ ] Open the notebook → the finished version → **Output**. Check `inference_log.csv` (how many "ok"?),
      the Dice table and warnings in Step 5, and every picture in `qc/`.
- [ ] Choose the **best 5 scans** (all organs visible, no warnings, clear images). Note why in 1 line each.
- [ ] Download `outputs/web_data.zip` and give it to B with the 5 case ids.

### Intern B
- [ ] In the repo: delete `docs/data/`, unzip `web_data.zip` inside `docs/`. (Use GitHub Desktop or git for this –
      the GitHub website cannot delete a whole folder in one step.)
- [ ] Keep only the chosen 5: `python tools/select_cases.py docs/data <id1> <id2> <id3> <id4> <id5>`
      (or ask A to run it), then upload/commit `docs/data/`.
- [ ] Check every case on laptop and phone: loads in under ~10 s, masks sit on the right organs,
      Compare view works, downloads work.

### Both (afternoon)
- [ ] Spot-check 3 numbers in the website against `metrics_all.csv`.
- [ ] Click each organ name once in one case and confirm it jumps to the right organ.

**Proof by 5:30 pm:** the live link showing 5 real scans.

**If Kaggle failed:** tell DrRB in the morning stand-up. Plan B: rent a 24 GB GPU on Brev for 2–3 hours and run
`python -m pipeline.run_all --n-cases 10 --n-web 10` (see README).

---

## Day 3 – Tuesday 13 Oct · "Make it teach"

### Intern A
- [ ] Results summary (half a page): Dice per organ across the 10 scans (mean and lowest), time per scan,
      GPU memory, and 3 observations (which organs are hardest and why).
- [ ] Draft two lines of teaching notes per organ (location, one key relation) from a standard anatomy textbook.
      Faculty will check them on Wednesday.

### Intern B
- [ ] Polish: clear "How to use" help, case descriptions, nicer empty states, check colours in dark mode.
- [ ] Stretch (only if everything else is done): show the organ's teaching note when its name is clicked.

**4 pm: feature freeze with DrRB.** Anything not working by then moves to v1.0.

**Proof by 5:30 pm:** polished site + results summary draft.

---

## Day 4 – Wednesday 14 Oct · "v0.5 released"

- [ ] **Morning – fixes only.** Test on 2 laptops and 2 phones. Finish the README (add your names, screenshots).
- [ ] **12:00 – faculty review (20–30 min).** Write every comment in a GitHub issue. Fix 1–2 quick ones today.
- [ ] **Afternoon:** record a 2–3 minute demo video (screen recording with voice); make a one-slide summary
      (what it is, the link, the key numbers, next steps).
- [ ] Create a **GitHub release `v0.5`** (*Releases → Draft a new release*).
- [ ] **4 pm – live demo to DrRB.**

### Definition of done (all must be true)
- [ ] Public link opens on a phone and a laptop without installing anything.
- [ ] 5 real CT scans, each viewable in axial, coronal, sagittal and 3D.
- [ ] 12 organs switchable; Expert / AI / Compare views work.
- [ ] Dice and volume table per scan; numbers match `metrics_all.csv`.
- [ ] Downloads work (masks, CSV, label key).
- [ ] README with credits and "not for clinical use"; the Kaggle notebook reproduces every number.
- [ ] Demo video, one-slide summary, faculty feedback recorded, release `v0.5` tagged.

---

## Troubleshooting

| Problem | What to do |
|---|---|
| "No GPU" in Step 0 | Session options → Accelerator → GPU. Then *Run → Restart & clear outputs* and start again. |
| Download fails or is very slow | Check Internet is On; re-run the cell (it resumes). |
| VISTA-3D download fails | Re-run Step 3; it also tries a second source automatically. |
| "out of memory" | Usually handled automatically. If a scan still fails, skip it – there are spares. |
| A **!** warning (label mix-up, left/right swap) | Do not publish. Send the Step 6 picture to DrRB. |
| Site shows "Could not load data/cases.json" | Check the path is `docs/data/cases.json`; wait 2 minutes after a commit; hard refresh. |
| A file is over 25 MB | Re-export with `WEB_SPACING_MM = 2.5`. |
| Viewer blank on an old phone | It needs WebGL2; try another browser or device. |
| Site works online but not from your disk | Use `python -m http.server -d docs 8000` instead of double-clicking. |

## What the starter kit already does (and what it does not)

Tested before handover on a public sample CT: the dataset handling, case selection, the VISTA-3D command
(run on a CPU with stand-in weights to prove the inputs, outputs and orientation handling), the scores and their
warnings, the web export, and the viewer in a browser. **Not yet tested:** a run with the real VISTA-3D weights on a
GPU – that is your Day 1 job.
