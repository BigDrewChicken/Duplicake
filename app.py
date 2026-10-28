"""Duplicake: finds identical and near-duplicate photos with classical computer vision (no ML).

Per image we store: MD5 (exact copies), dHash, HSV colour histogram, luminance (lighting)
histogram, Canny edge map, FAST corner layout, and ORB keypoints + descriptors.
Pairs are pre-screened with the cheap global features, then verified by ORB descriptor
matching with RANSAC geometry. Matching photos are grouped into batches.
"""

import hashlib
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, abort, jsonify, render_template, request, send_file
from send2trash import send2trash

EXTS = {".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".bmp", ".webp", ".tif", ".tiff"}
SIDE = 512            # longest side used for analysis
PRESCREEN = 0.55      # global-feature score a pair needs before ORB verification
WORKERS = min(8, os.cpu_count() or 2)
W = dict(hash=.30, edge=.20, fast=.10, hsv=.28, light=.12)  # global score weights (sum = 1)

app = Flask(__name__)
JOBS, THUMBS, KNOWN = {}, {}, set()   # KNOWN = paths found by scans (only these can be served/deleted)


# ---------------------------------------------------------------- feature extraction
def find_images(root):
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if Path(f).suffix.lower() in EXTS:
                yield os.path.join(dirpath, f)


def extract(path):
    try:
        raw = np.fromfile(path, np.uint8)
        img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h0, w0 = img.shape[:2]
        k = SIDE / max(h0, w0)
        if k < 1:
            img = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, w = gray.shape

        small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)            # dHash, 64 bits
        dhash = (small[:, 1:] > small[:, :-1]).flatten().astype(np.float32)

        def sqrt_hist(hist):                                                       # unit-norm sqrt => dot = Bhattacharyya
            hist = hist.flatten()
            return np.sqrt(hist / (hist.sum() + 1e-9)).astype(np.float32)

        colour = sqrt_hist(cv2.calcHist([hsv], [0, 1, 2], None, [12, 4, 4], [0, 180, 0, 256, 0, 256]))
        light = sqrt_hist(cv2.calcHist([hsv], [2], None, [32], [0, 256]))

        med = float(np.median(gray))                                               # edges: 8x8 density map
        lo = int(max(10, .66 * med))
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), lo, int(min(250, max(lo + 30, 1.33 * med))))
        edge = cv2.resize(edges.astype(np.float32) / 255, (8, 8), interpolation=cv2.INTER_AREA).flatten()

        fast_kp = cv2.FastFeatureDetector_create(threshold=20).detect(gray)        # FAST corners: 8x8 layout
        pts = np.array([p.pt for p in fast_kp], np.float32).reshape(-1, 2)
        fast = np.histogram2d(pts[:, 1], pts[:, 0], bins=8, range=[[0, h], [0, w]])[0].flatten().astype(np.float32)

        kp, des = cv2.ORB_create(nfeatures=500, fastThreshold=20).detectAndCompute(gray, None)
        orb_pts = np.array([p.pt for p in kp], np.float32).reshape(-1, 2)

        s = min(1.0, 360 / max(h, w))
        thumb = img if s >= 1 else cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        return dict(
            path=path, md5=hashlib.md5(raw).hexdigest(), w=w0, h=h0, px=w0 * h0, bytes=int(raw.size),
            sharp=float(cv2.Laplacian(gray, cv2.CV_64F).var()), expo=1 - abs(float(gray.mean()) - 128) / 128,
            hash=dhash, hsv=colour, light=light, edge=edge, fast=fast, des=des, pts=orb_pts, link=0.0,
            thumb=cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes(),
        )
    except Exception:
        return None


# ---------------------------------------------------------------- comparison
def unit(M):
    M = M - M.mean(1, keepdims=True)
    return M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)


def prescreen(F):
    """Vectorised global similarity for every pair; returns {(i, j): score} above PRESCREEN."""
    if len(F) < 2:
        return {}
    H = np.stack([f["hash"] for f in F]); Hn = 1 - H
    C = np.stack([f["hsv"] for f in F]); L = np.stack([f["light"] for f in F])
    E = unit(np.stack([f["edge"] for f in F])); G = unit(np.stack([f["fast"] for f in F]))
    out = {}
    for s in range(0, len(F), 256):
        sl = slice(s, s + 256)
        hs = np.clip(((H[sl] @ H.T + Hn[sl] @ Hn.T) / 64 - .5) * 2, 0, 1)   # 0.5 = unrelated hashes
        g = (W["hash"] * hs + W["edge"] * np.clip(E[sl] @ E.T, 0, 1) + W["fast"] * np.clip(G[sl] @ G.T, 0, 1)
             + W["hsv"] * (C[sl] @ C.T) + W["light"] * (L[sl] @ L.T))
        for a, b in zip(*np.nonzero(g >= PRESCREEN)):
            i = int(a) + s
            if b > i:
                out[(i, int(b))] = float(g[a, b])
    return out


def orb_score(a, b):
    """ORB descriptor matching + RANSAC similarity transform. None when there are too few keypoints."""
    if a["des"] is None or b["des"] is None or min(len(a["des"]), len(b["des"])) < 15:
        return None
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(a["des"], b["des"], k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < .75 * p[1].distance]
    if len(good) < 6:
        return 0.0
    src = a["pts"][[m.queryIdx for m in good]]
    dst = b["pts"][[m.trainIdx for m in good]]
    _, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=4.0)
    inliers = int(inl.sum()) if inl is not None else 0
    return min(1.0, inliers / (.35 * min(len(a["des"]), len(b["des"]))))


def pick_best(items):
    top = lambda k: max(i[k] for i in items) or 1
    for i in items:
        i["q"] = .4 * i["px"] / top("px") + .3 * i["sharp"] / top("sharp") + .15 * i["bytes"] / top("bytes") + .15 * i["expo"]
    best = max(items, key=lambda i: i["q"])
    why = [t for k, t in (("px", "highest resolution"), ("sharp", "sharpest"), ("bytes", "largest file")) if best[k] >= top(k)]
    return best, ("Best pick: " + ", ".join(why)) if why else "Best pick: most balanced overall"


def run_scan(job, root, thr):
    t0 = time.time()
    try:
        job["stage"] = "finding"
        paths = [os.path.abspath(p) for p in find_images(root)]
        KNOWN.update(paths)
        job.update(stage="reading", total=len(paths), done=0)
        feats = []
        with ThreadPoolExecutor(WORKERS) as ex:
            for i, f in enumerate(ex.map(extract, paths), 1):
                if f:
                    THUMBS[f["path"]] = f.pop("thumb")
                    feats.append(f)
                job["done"] = i
        n = len(feats)

        job.update(stage="comparing", done=0, total=0)
        cand = prescreen(feats)
        keys = list(cand)
        job["total"] = len(keys)

        def verify(key):
            a, b, g = feats[key[0]], feats[key[1]], cand[key]
            if a["md5"] == b["md5"]:
                return 1.0
            o = orb_score(a, b)
            return g if o is None else max(.35 * g + .65 * o, g - .1)

        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        with ThreadPoolExecutor(WORKERS) as ex:
            for k, s in enumerate(ex.map(verify, keys), 1):
                job["done"] = k
                if s >= thr:
                    i, j = keys[k - 1]
                    parent[find(i)] = find(j)
                    feats[i]["link"] = max(feats[i]["link"], s)
                    feats[j]["link"] = max(feats[j]["link"], s)

        buckets = {}
        for i in range(n):
            buckets.setdefault(find(i), []).append(feats[i])
        groups = []
        for items in buckets.values():
            if len(items) < 2:
                continue
            same = len({f["md5"] for f in items}) == 1
            if same:
                best, why = min(items, key=lambda f: len(f["path"])), "Exact copies: any one will do"
            else:
                best, why = pick_best(items)
            items.sort(key=lambda f: (f is not best, -f["px"]))
            groups.append(dict(
                kind="Identical" if same else "Near-duplicate", why=why,
                items=[dict(path=f["path"], name=os.path.basename(f["path"]), w=f["w"], h=f["h"],
                            bytes=f["bytes"], best=f is best, match=round(100 * f["link"])) for f in items]))
        groups.sort(key=lambda g: -sum(i["bytes"] for i in g["items"] if not i["best"]))
        for k, g in enumerate(groups, 1):
            g["id"] = k
        stats = dict(images=n, folders=len({os.path.dirname(p) for p in paths}), skipped=len(paths) - n,
                     seconds=round(time.time() - t0, 1))
        job.update(stage="done", result=dict(groups=groups, stats=stats))
    except Exception as e:  # surface any failure to the UI
        job.update(stage="error", error=str(e))


# ---------------------------------------------------------------- routes
@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/scan")
def scan():
    d = request.get_json(force=True)
    root = os.path.abspath(os.path.expanduser(str(d.get("path", "")).strip()))
    if not os.path.isdir(root):
        return jsonify(error="That folder doesn't exist. Check the path and try again."), 400
    thr = min(.95, max(.6, float(d.get("threshold", .78))))
    jid = uuid.uuid4().hex
    JOBS[jid] = dict(stage="queued", done=0, total=0, result=None, error=None)
    threading.Thread(target=run_scan, args=(JOBS[jid], root, thr), daemon=True).start()
    return jsonify(job=jid)


@app.get("/api/job/<jid>")
def job(jid):
    if jid not in JOBS:
        abort(404)
    return jsonify(JOBS[jid])


@app.get("/api/thumb")
def thumb():
    data = THUMBS.get(os.path.abspath(request.args.get("p", "")))
    if data is None:
        abort(404)
    return Response(data, mimetype="image/jpeg", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/image")
def image():
    p = os.path.abspath(request.args.get("p", ""))
    if p not in KNOWN or not os.path.isfile(p):
        abort(404)
    return send_file(p)


@app.post("/api/delete")
def delete():
    d = request.get_json(force=True)
    permanent = bool(d.get("permanent"))
    done, failed = [], []
    for p in d.get("paths", []):
        p = os.path.abspath(p)
        try:
            if p not in KNOWN:
                raise PermissionError
            os.remove(p) if permanent else send2trash(p)
            KNOWN.discard(p)
            THUMBS.pop(p, None)
            done.append(p)
        except Exception:
            failed.append(p)
    return jsonify(deleted=done, failed=failed)


@app.get("/api/browse")
def browse():
    p = os.path.abspath(os.path.expanduser(request.args.get("p") or "~"))
    if not os.path.isdir(p):
        p = str(Path.home())
    try:
        names = sorted((n for n in os.listdir(p) if not n.startswith(".") and os.path.isdir(os.path.join(p, n))), key=str.lower)
    except OSError:
        names = []
    parent = os.path.dirname(p)
    drives = [f"{c}:\\" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{c}:\\")] if os.name == "nt" else []
    return jsonify(path=p, parent=parent if parent != p else None, drives=drives,
                   dirs=[dict(name=n, path=os.path.join(p, n)) for n in names])


if __name__ == "__main__":
    print("Duplicake is baking at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
