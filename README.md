<div align="center">

# Duplicake

### Find your duplicate slices (photos, hehe)

A web app that scans a folder (and every folder inside it) for **identical and near-identical photos**, groups them into batches, and helps you keep the best slice and delete the rest. It compares photos with classical computer vision: FAST corners, ORB features, edges, HSV colours, and lighting.

[![Python](https://img.shields.io/badge/Python-3.10%2B-FFB3C6?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/) [![Flask](https://img.shields.io/badge/Flask-Backend-FFE08A?style=for-the-badge&logo=flask&logoColor=black)](https://flask.palletsprojects.com/) [![OpenCV](https://img.shields.io/badge/OpenCV-FAST%20%2B%20ORB-FF8FAB?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/) [![NumPy](https://img.shields.io/badge/NumPy-Scoring-FFF0B3?style=for-the-badge&logo=numpy&logoColor=black)](https://numpy.org/)

[![HTML5](https://img.shields.io/badge/HTML5-Frontend-FFB3C6?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML) [![CSS3](https://img.shields.io/badge/CSS3-Cake%20Styling-FFE08A?style=for-the-badge&logo=css3&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/CSS) [![JavaScript](https://img.shields.io/badge/JavaScript-Batch%20UI-FF8FAB?style=for-the-badge&logo=javascript&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/JavaScript) [![Git](https://img.shields.io/badge/Git-Version%20Control-FFF0B3?style=for-the-badge&logo=git&logoColor=black)](https://git-scm.com/)

</div>

* * *

## Table of Contents

- [About the Project](#about-the-project)
- [Features](#features)
- [How It Works](#how-it-works)
  - [The Features We Store](#the-features-we-store)
  - [How Two Photos Get Scored](#how-two-photos-get-scored)
  - [How the Best Slice Is Picked](#how-the-best-slice-is-picked)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Get the code](#1-get-the-code)
  - [2. Create the virtual environment](#2-create-the-virtual-environment)
  - [3. Activate the virtual environment](#3-activate-the-virtual-environment)
  - [4. Install the dependencies](#4-install-the-dependencies)
  - [5. Run Duplicake](#5-run-duplicake)
  - [6. Open it in your browser](#6-open-it-in-your-browser)
  - [7. Stop the server](#7-stop-the-server)
- [Understanding the Virtual Environment](#understanding-the-virtual-environment)
- [Using Duplicake](#using-duplicake)
- [Try It with Sample Photos](#try-it-with-sample-photos)
- [Tuning the Recipe](#tuning-the-recipe)
- [API Reference](#api-reference)
- [Replicating the Project from Scratch](#replicating-the-project-from-scratch)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [License](#license)
- [Project Creators](#project-creators)

* * *

## About the Project

**Duplicake** helps you clean up photo folders full of copies, re-saves, resized exports, and burst shots. Point it at a folder, press **Find Duplicakes**, and it walks through every subfolder, studies each photo, and returns **batches** of photos that look alike.

Each batch is shown like a batch of photos in a Messenger or Instagram chat: a small collage thumbnail on top, then a swipeable row of photos with numbered selection circles. One photo in every batch wears a **Best slice** crown, so you can keep it and delete the rest with a single click.

The interface is dressed as a cake: pastel pink and butter-yellow layers, a frosting-drip header, and rounded-square cards everywhere.

## Features

- **Recursive scanning.** Every subfolder is searched for supported image files. Hidden folders (names starting with a dot) are skipped.
- **Exact and near-duplicate detection.** Byte-identical files are marked **Identical**. Resized, recompressed, brightened, or slightly shifted copies are marked **Near-duplicate**.
- **No machine learning.** Detection uses FAST, ORB, Canny edges, HSV colour histograms, lighting histograms, and a perceptual hash.
- **Batches.** Matching photos are grouped together, with the batches that free the most space listed first.
- **Best slice suggestion.** Each batch recommends one photo to keep, using resolution, sharpness, file size, and exposure.
- **Quick delete buttons.** *Select all but best*, *Delete selected*, *Keep best, delete the rest*, and a global *Keep the best of every batch*.
- **Safe deletes by default.** Photos go to the Recycle Bin or Trash. A checkbox switches to permanent deletion.
- **Strictness slider.** Choose between looser (more batches) and stricter (near-identical only).
- **Built-in folder picker.** Browse to a folder instead of typing the path.
- **Live progress.** A candy-stripe progress bar shows reading and comparing progress.
- **Responsive and accessible.** Works on small screens, supports keyboard selection (Tab, then Space or Enter), and respects reduced-motion settings.

## How It Works

```
You pick a folder and press "Find Duplicakes"
        |
        v
  app.js  --POST /api/scan-->  app.py (Flask)
                                  |
                       background thread starts
                                  |
        +-------------------------+---------------------------+
        |                                                     |
 1. Find images (os.walk)                          2. Read each photo (parallel)
    jpg, png, bmp, webp, tif ...                      MD5, dHash, HSV, lighting,
                                                      edges, FAST, ORB
        |                                                     |
        +-------------------------+---------------------------+
                                  |
                  3. Pre-screen every pair (NumPy, vectorised)
                     cheap global score >= 0.55 becomes a candidate
                                  |
                  4. Verify candidates with ORB + RANSAC
                     final score >= strictness  -->  linked
                                  |
                  5. Union linked photos into batches
                     pick a Best slice for each batch
                                  |
  app.js  <--poll /api/job/<id>---+
        |
        v
 Batches appear. Select photos or use the quick buttons, then
 POST /api/delete  -->  Recycle Bin / Trash (or permanent delete)
```

1. The browser sends the folder path and strictness to `/api/scan`. The server starts a background thread and returns a job id.
2. The browser polls `/api/job/<id>` every 0.4 seconds to update the progress bar.
3. The server finds every supported image, reads each one once with OpenCV, and stores its features in memory.
4. Every pair of photos gets a fast global similarity score. Pairs above the pre-screen cutoff are verified with ORB keypoint matching.
5. Photos whose final score meets the strictness setting are linked, and linked photos form a batch.
6. When the job finishes, the browser receives the batches and draws them.

### The Features We Store

Every photo is analysed once, at a maximum side length of 512 pixels. This is what Duplicake keeps for each one:

| Feature                | How it is made                                                    | What it catches                               |
|------------------------|-------------------------------------------------------------------|-----------------------------------------------|
| **MD5 hash**           | Hash of the raw file bytes                                        | Exact copies, even when renamed or moved      |
| **dHash (64 bits)**    | 9x8 grayscale thumbnail, compare neighbouring pixels              | Overall structure, resizing, recompression    |
| **HSV colour profile** | 12 x 4 x 4 histogram of hue, saturation, value                    | Colour palette of the photo                   |
| **Lighting profile**   | 32-bin histogram of the V (brightness) channel                    | Exposure and lighting distribution            |
| **Edge map**           | Canny edges (auto thresholds), summed into an 8x8 density grid    | Where the outlines and detail are             |
| **FAST corner layout** | FAST corner detector, counted into an 8x8 grid                    | Where the corners and texture are             |
| **ORB keypoints**      | Up to 500 ORB keypoints with 256-bit binary descriptors           | Same content after resize, shift, or rotation |

ORB finds its keypoints with the FAST detector internally, so FAST appears twice: once as a layout map for pre-screening, and once inside ORB for matching.

### How Two Photos Get Scored

**Step 1: global score (every pair, fast).** Five similarity values between 0 and 1 are blended:

| Part            | Weight | Compared with                                        |
|-----------------|--------|------------------------------------------------------|
| dHash           | 0.30   | Hamming similarity (random hashes count as 0)        |
| HSV colour      | 0.28   | Bhattacharyya coefficient                            |
| Edge map        | 0.20   | Correlation of the 8x8 grids                         |
| Lighting        | 0.12   | Bhattacharyya coefficient                            |
| FAST layout     | 0.10   | Correlation of the 8x8 grids                         |

This step is done for all pairs at once with NumPy matrix maths, in chunks of 256 rows, so it stays fast on large folders. Pairs scoring **0.55 or higher** become candidates.

**Step 2: ORB verification (candidates only).** Descriptors are matched with a brute-force Hamming matcher and Lowe's ratio test (0.75). RANSAC then fits a rotation, scale, and shift between the matched points, and the number of agreeing points (inliers) becomes the ORB score. This step is what separates a true duplicate from a merely similar photo.

**Step 3: final score.**

```
exact same bytes (MD5)        -> 1.00
ORB available                 -> max( 0.35 x global + 0.65 x ORB ,  global - 0.10 )
fewer than 15 keypoints       -> global score only (flat graphics, screenshots)
```

Two photos are linked when their final score is at or above the **strictness** slider (default 78%). Linked photos are merged into one batch.

### How the Best Slice Is Picked

Within each batch, every photo gets a quality score, with each measure scaled against the best in that batch:

| Measure                                       | Weight |
|-----------------------------------------------|--------|
| Resolution (width x height of the original)   | 0.40   |
| Sharpness (variance of the Laplacian)         | 0.30   |
| File size                                     | 0.15   |
| Exposure (closeness to mid-brightness)        | 0.15   |

The highest score wears the crown, and its card says why (for example, *highest resolution, sharpest*). For batches of byte-identical copies, the photo with the shortest file path is kept, which is usually the original rather than `Copy (1)`.

## Tech Stack

| Layer              | Technology                                            |
|--------------------|-------------------------------------------------------|
| Language           | Python 3.10+                                          |
| Web framework      | Flask                                                 |
| Computer vision    | OpenCV (`opencv-python-headless`): FAST, ORB, Canny   |
| Numerics           | NumPy                                                 |
| Safe deletion      | Send2Trash                                            |
| Frontend           | HTML5, CSS3, vanilla JavaScript                       |
| Fonts              | Fredoka (Google Fonts, falls back to Trebuchet MS)    |

## Project Structure

```
duplicake/
├── static/
│   ├── css/
│   │   └── style.css        # Pastel pink and yellow cake styling
│   └── js/
│       └── app.js           # Scan flow, batch UI, selection, delete buttons
├── templates/
│   └── index.html           # The single page of the app
├── app.py                   # Flask server, feature extraction, matching, API
├── requirements.txt         # Python dependencies
├── .gitignore               # Keeps __pycache__, venvs, editor files out of Git
└── README.md
```

Duplicake has no database and writes nothing to disk. All results and thumbnails live in memory and disappear when the server stops.

* * *

## Getting Started

Follow these steps in order. They work the same on any computer; only the activation command in step 3 differs between Windows and macOS/Linux.

### Prerequisites

Make sure you have these installed before you begin:

| Tool           | Version            | Check with         |
|----------------|--------------------|--------------------|
| Python         | 3.10 or newer      | `python --version` |
| pip            | Comes with Python  | `pip --version`    |
| Git (optional) | Any recent version | `git --version`    |

You also need a modern browser (Chrome, Edge, Firefox, or Safari) and an internet connection the first time you open the page, so the Fredoka font can load. Without internet, everything still works with a fallback font.

> **Windows tip:** When installing Python, tick **"Add python.exe to PATH"** on the first installer screen. If `python` is not recognized later, this is almost always why.

### 1. Get the code

Clone the repository (or download it as a ZIP and extract it):

```
git clone <your-repository-url>
cd duplicake
```

Replace `<your-repository-url>` with the actual link to the repository. If you received a ZIP, extract it and open a terminal inside the extracted `duplicake` folder.

### 2. Create the virtual environment

A virtual environment (`.venv`) is a private folder that holds this project's Python packages, so they do not clash with other projects on your computer. From inside the `duplicake` folder, run:

```
python -m venv .venv
```

This creates a `.venv` folder. You only need to do this **once per computer**.

### 3. Activate the virtual environment

You must activate the environment **every time you open a new terminal** to work on Duplicake.

**Windows (PowerShell or the VS Code terminal):**

```
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**

```
.venv\Scripts\activate.bat
```

**macOS / Linux:**

```
source .venv/bin/activate
```

When it works, your terminal prompt starts with `(.venv)`, like this:

```
(.venv) PS C:\Users\you\duplicake>
```

> **PowerShell says "running scripts is disabled"?** Run this once, then try activating again:
>
> ```
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### 4. Install the dependencies

With `(.venv)` showing in your prompt, install everything Duplicake needs:

```
pip install -r requirements.txt
```

This installs Flask, OpenCV (headless build), NumPy, and Send2Trash. The OpenCV download is the largest part, so give it a minute.

If `pip` complains about a missing wheel or an old version, upgrade it first and try again:

```
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> **Important:** Install `opencv-python-headless` only. Having both `opencv-python` and `opencv-python-headless` in the same environment can cause import errors. Duplicake never opens an OpenCV window, so the headless build is all it needs.

### 5. Run Duplicake

Still inside the activated environment, start the Flask server:

```
python app.py
```

You should see output similar to this:

```
Duplicake is baking at http://127.0.0.1:5000
 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000
```

Leave this terminal open. The server runs for as long as the window stays open.

### 6. Open it in your browser

Go to:

```
http://127.0.0.1:5000
```

(`http://localhost:5000` works too.) Type or browse to a folder of photos and press **Find Duplicakes**.

> If your terminal shows a different port, use that one instead.

### 7. Stop the server

Click the terminal running the server and press **Ctrl + C**. To leave the virtual environment, type:

```
deactivate
```

* * *

## Understanding the Virtual Environment

**What is `.venv`?** It is a folder containing its own copy of Python plus only the packages Duplicake needs (Flask, OpenCV, NumPy, and Send2Trash). When it is *activated*, the `python` and `pip` commands in your terminal use this private copy instead of the one installed system-wide.

**Why use one?**

- Different projects can use different package versions without breaking each other.
- Anyone who clones the repository can recreate the exact same setup.
- Your global Python stays clean.

**What is `requirements.txt`?** A plain list of the packages the project depends on. `pip install -r requirements.txt` reads that list and installs everything in one go. After adding a new package, you can pin the exact versions you tested with:

```
pip freeze > requirements.txt
```

**Why is `.venv` not in the repository?** The folder is large and specific to each computer, so it is listed in `.gitignore` and is never uploaded. Each person creates their own with steps 2 to 4 above. The `.gitignore` also keeps `__pycache__/`, editor folders, and `.env` files out of Git.

**Environment variables?** Duplicake does not require any. Everything runs with the defaults.

**Common mistake:** running `python app.py` *without* `(.venv)` active. If you get `ModuleNotFoundError: No module named 'flask'` (or `'cv2'`), your environment is not activated, so go back to step 3.

## Using Duplicake

1. **Choose a folder.** Type a full path, or press **Browse** and click through folders, then **Use this folder**. Subfolders are scanned automatically.
   - Windows example: `C:\Users\you\Pictures`
   - macOS example: `/Users/you/Pictures`
   - Linux example: `/home/you/Pictures`
2. **Set the strictness.** The default is 78%. Slide toward **Looser** to catch more loosely similar photos, or toward **Stricter** to see only near-identical ones.
3. **Press Find Duplicakes.** The progress bar moves through *Reading photos* and *Comparing photos*.
4. **Read the summary.** The four tiles show photos scanned, folders with photos, batches found, and space that can be freed.
5. **Review each batch.** Swipe or scroll the photo row. Each photo shows its file name, size in pixels, file size, and match percentage. Press **Open** on a photo to see it at full size in a new tab.
6. **Select or delete.**

| Button                           | What it does                                                           |
|----------------------------------|------------------------------------------------------------------------|
| Tap a photo                      | Selects or unselects it (numbered circle in the corner)                |
| **Select all but best**          | Selects every photo in the batch except the crowned one                |
| **Delete selected (n)**          | Deletes only the photos you selected in that batch                     |
| **Keep best, delete N**          | Deletes everything in the batch except the crowned photo               |
| **Keep the best of every batch** | Does the above for every batch at once                                 |
| **Delete permanently** checkbox  | Skips the Recycle Bin / Trash. This cannot be undone                   |

Every delete asks for confirmation first. After deleting, a batch with fewer than two photos left disappears. If you delete the crowned photo and keep others, the remaining photo with the highest resolution becomes the new Best slice.

> **Tip:** Skim the thumbnails before using the bulk buttons. Batches are built by chaining matches (see [Known Limitations](#known-limitations)), so occasionally a batch holds a photo that is only loosely related.

## Try It with Sample Photos

Save this as `make_samples.py` in the project folder and run it inside the activated environment. It draws a synthetic photo, then makes an exact copy, a small low-quality re-save, and a brighter version, plus one unrelated image.

```python
import os, shutil
import cv2
import numpy as np

def scene(seed):
    r = np.random.default_rng(seed)
    img = np.full((600, 800, 3), r.integers(60, 200, 3), np.uint8)
    for _ in range(40):
        color = tuple(int(x) for x in r.integers(0, 255, 3))
        p1 = tuple(int(x) for x in r.integers(0, [800, 600]))
        p2 = tuple(int(x) for x in r.integers(0, [800, 600]))
        if r.random() < .5:
            cv2.rectangle(img, p1, p2, color, -1)
        else:
            cv2.circle(img, p1, int(r.integers(10, 80)), color, -1)
    return img

os.makedirs("samples/vacation", exist_ok=True)
a, b = scene(1), scene(2)
cv2.imwrite("samples/original.jpg", a)
cv2.imwrite("samples/vacation/original_small.jpg", cv2.resize(a, (400, 300)), [cv2.IMWRITE_JPEG_QUALITY, 40])
cv2.imwrite("samples/brighter.png", np.clip(a.astype(int) + 35, 0, 255).astype(np.uint8))
shutil.copy("samples/original.jpg", "samples/original - Copy.jpg")
cv2.imwrite("samples/unrelated.jpg", b)
print("Sample photos baked in ./samples")
```

```
python make_samples.py
python app.py
```

Then scan the `samples` folder (use the full path). With the default strictness you should see **one batch of four photos**: the original, its copy, the small re-save, and the brighter version. The unrelated image is left out. Delete the `samples` folder when you are done.

## Tuning the Recipe

Start with the **Strictness** slider in the page. If that is not enough, these constants are at the top of `app.py`:

| Setting                | Location in `app.py`                      | Default | Effect                                                                                       |
|------------------------|-------------------------------------------|---------|----------------------------------------------------------------------------------------------|
| `SIDE`                 | Top of file                               | 512     | Longest side used for analysis. Larger is more detailed but slower                           |
| `PRESCREEN`            | Top of file                               | 0.55    | Global score a pair needs before ORB runs. Lower catches more edited copies but is slower    |
| `W`                    | Top of file                               | see above | Weights of the five global features                                                        |
| `WORKERS`              | Top of file                               | up to 8 | Threads for reading and matching photos                                                      |
| `nfeatures`            | `cv2.ORB_create(...)` in `extract`        | 500     | ORB keypoints stored per photo                                                               |
| `threshold` (FAST)     | `cv2.FastFeatureDetector_create(...)`     | 20      | Corner sensitivity. Lower finds more corners                                                 |
| Ratio test             | `orb_score`                               | 0.75    | Lower is stricter when matching ORB descriptors                                              |
| `ransacReprojThreshold`| `orb_score`                               | 4.0 px  | How closely matched points must agree geometrically                                          |
| Supported formats      | `EXTS` at the top of the file             | see below | Add or remove file extensions                                                              |
| Port                   | `app.run(...)` at the bottom              | 5000    | Change if 5000 is busy                                                                       |

**Supported formats:** `.jpg`, `.jpeg`, `.jpe`, `.jfif`, `.png`, `.bmp`, `.webp`, `.tif`, `.tiff`.

After changing any value, stop the server (Ctrl + C) and run `python app.py` again.

## API Reference

| Method and route       | Purpose                                                                             |
|------------------------|-------------------------------------------------------------------------------------|
| `GET /`                | Serves the page                                                                     |
| `POST /api/scan`       | Body: `{"path": "...", "threshold": 0.78}`. Starts a scan and returns `{"job": id}` |
| `GET /api/job/<id>`    | Returns `stage`, `done`, `total`, and finally `result` (batches and stats)          |
| `GET /api/thumb?p=...` | A 360px JPEG thumbnail of a scanned photo, served from memory                       |
| `GET /api/image?p=...` | The full-size original of a scanned photo                                           |
| `POST /api/delete`     | Body: `{"paths": [...], "permanent": false}`. Moves to Trash or deletes             |
| `GET /api/browse?p=...`| Lists subfolders for the folder picker                                              |

Photos can only be viewed or deleted if a scan found them first, so the API cannot be used to read or remove arbitrary files by guessing paths.

## Replicating the Project from Scratch

**Option A: copy the project.** Copy the whole `duplicake` folder (or the ZIP) to the new computer, leave out `.venv`, then follow steps 2 to 6 above. Nothing else needs to move, because Duplicake keeps no saved data.

**Option B: rebuild it by hand.** Create this layout and place each file's code inside:

```
duplicake/
├── app.py
├── requirements.txt
├── templates/index.html
└── static/
    ├── css/style.css
    └── js/app.js
```

`requirements.txt` contains:

```
Flask>=3.0
opencv-python-headless>=4.9
numpy>=1.26
Send2Trash>=1.8
```

Then create the environment and install as in steps 2 to 4.

**Option C: put it on GitHub.**

```
git init
git add .
git commit -m "Bake Duplicake"
git branch -M main
git remote add origin <your-repository-url>
git push -u origin main
```

The included `.gitignore` keeps `__pycache__/`, virtual environments, editor settings, logs, and `.env` out of the repository.

**Platform notes**

| Platform | Notes                                                                                                                                      |
|----------|--------------------------------------------------------------------------------------------------------------------------------------------|
| Windows  | Use `python` (or `py`) and the `.venv\Scripts\...` activation commands. Folder picker shows drive letters                                  |
| macOS    | Use `python3` if `python` is not found. Port 5000 can be taken by AirPlay Receiver, so change the port or turn that setting off            |
| Linux    | Use `python3` and `source .venv/bin/activate`. Moving to Trash needs a desktop environment that supports the standard Trash folder         |

> **Safety note:** The server listens on `127.0.0.1` only, so nobody else on your network can reach it. Duplicake can delete files, so do not change the host to `0.0.0.0` unless you understand the risk.

## Known Limitations

- **Not tuned on every library.** The default strictness and pre-screen cutoff are sensible starting points. They were checked with synthetic test images, so real photo collections may call for a different strictness.
- **Batches chain.** If photo A matches B and B matches C, all three land in one batch even if A and C look quite different. Check thumbnails before bulk deleting.
- **Heavy edits can slip through.** Very aggressive crops, large rotations, or heavy filters can fall below the pre-screen cutoff and never reach ORB verification. Lowering `PRESCREEN` helps at the cost of speed.
- **Burst shots can look alike.** Photos of the same scene with small changes may be grouped at looser settings. Raise the strictness for them.
- **Some formats are not read.** HEIC, GIF, RAW, and other formats OpenCV cannot decode are skipped and reported as unreadable.
- **Results are not saved.** Restarting the server clears results and thumbnails. Scan again to rebuild them.
- **One user, one machine.** It is a local tool, not a multi-user service.
- **Large collections take time.** Reading and matching thousands of photos can take several minutes. The progress bar shows how far along it is.

## Troubleshooting

| Problem                                                | Likely cause and fix                                                                                                           |
|--------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| `python` is not recognized                             | Python is not on your PATH. Reinstall it and tick "Add to PATH", or try `py` (Windows) or `python3` (macOS/Linux)              |
| `ModuleNotFoundError: No module named 'flask'` or `'cv2'` | The virtual environment is not activated, or dependencies are not installed. Redo steps 3 and 4                             |
| PowerShell blocks `Activate.ps1`                       | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, then activate again                                |
| `pip install` fails on OpenCV                          | Upgrade pip (`python -m pip install --upgrade pip`) and make sure Python is 3.10 or newer                                      |
| `ImportError` mentioning `cv2` after install           | Both `opencv-python` and `opencv-python-headless` are installed. Uninstall both, then run `pip install -r requirements.txt`    |
| `Address already in use` / port 5000 busy              | Another program (on macOS, often AirPlay Receiver) uses the port. Close it, or change the port in the `app.run(...)` line      |
| "That folder doesn't exist"                            | Check the path for typos, remove surrounding quotes, and use the full path. `~` works for your home folder                     |
| Scan finishes with zero batches                        | No pairs met the strictness. Slide it toward **Looser** and scan again                                                         |
| Far too many batches                                   | Slide toward **Stricter**, or raise `PRESCREEN` in `app.py`                                                                    |
| "N files couldn't be read and were skipped"            | Those files are corrupted or in a format OpenCV cannot decode, such as HEIC                                                    |
| Photos show as broken images                           | The server restarted, so thumbnails were cleared. Press **Find Duplicakes** again                                              |
| A delete fails                                         | The file is open in another program, is read-only, or Trash is unavailable on this system. Close the program, or tick **Delete permanently** |
| Page looks unstyled or old after an edit               | The browser cached the old file. Hard refresh with **Ctrl + Shift + R**                                                        |
| Font looks plain                                       | You are offline, so the Fredoka font could not load. The fallback font is used and everything still works                      |
| Scan is slow                                           | Close heavy programs, lower `SIDE`, or raise `PRESCREEN`. Reading very large photos is the slowest part                        |

## License



* * *

## Project Creator

[![Ross Andrew Bulaong](https://img.shields.io/badge/Bulaong%2C%20Ross%20Andrew-FFB3C6?style=for-the-badge&logo=github&logoColor=black)](https://github.com/BigDrewChicken)
