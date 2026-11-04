"""Rules that turn symbol detections + map dashes into 1880 classes.

Same method as step 06c of the peatland-rewetting-sh project
(https://github.com/bonnietilse-design/peatland-rewetting-sh), applied with
the thresholds tuned there (rule_parameters.json). Pure NumPy/SciPy + GDAL,
so it runs in QGIS's own Python.
"""
import numpy as np
from scipy import ndimage as nd
from scipy.spatial import cKDTree

CELL = 25                                   # m, output grid
NAMES = {0: "", 1: "Moor", 2: "nasse Wiese", 3: "Heide"}
DASH = {"max_h": 3, "min_w": 5, "max_w": 40, "window": 5, "tuft_base_m": 10,
        "field_res": 5, "field_line_m": 80, "field_min_ha": 0.2, "field_max_ha": 40}
TORF_RECUR_CELLS = 11                       # 275 m window for "recurring" Torfstich


def dash_density(band, width, height, n_r, n_c, tuft_xy, chunk=2500, margin=60, feedback=None):
    """Count dashes (flat ink marks) per 25 m cell and find the map's field lines.

    band: GDAL band of a 1 m map where ink = 1 and paper = 0 (already converted).
    tuft_xy: tuft positions in pixel coordinates (col, row) - flat marks next to a
    tuft are its base line, not a dash.
    """
    tree = cKDTree(tuft_xy) if len(tuft_xy) else None
    g = np.zeros((n_r, n_c))
    f = DASH["field_res"]
    g5 = np.zeros((height // f, width // f))
    line5 = np.zeros((height // f, width // f), bool)
    total = 0
    steps = len(range(0, height, chunk)) * len(range(0, width, chunk))
    done = 0
    for y0 in range(0, height, chunk):
        for x0 in range(0, width, chunk):
            if feedback is not None and feedback.isCanceled():
                return None
            xa, ya = max(0, x0 - margin), max(0, y0 - margin)
            xb, yb = min(width, x0 + chunk + margin), min(height, y0 + chunk + margin)
            ink = band.ReadAsArray(xa, ya, xb - xa, yb - ya) > 0
            lab, n = nd.label(ink, structure=np.ones((3, 3)))
            done += 1
            if feedback is not None:
                feedback.setProgress(60 + 30 * done / steps)
            if n == 0:
                continue
            sl = nd.find_objects(lab)
            h = np.array([s[0].stop - s[0].start for s in sl])
            w = np.array([s[1].stop - s[1].start for s in sl])
            cy = np.array([(s[0].start + s[0].stop) // 2 for s in sl]) + ya
            cx = np.array([(s[1].start + s[1].stop) // 2 for s in sl]) + xa
            core = (cx >= x0) & (cx < x0 + chunk) & (cy >= y0) & (cy < y0 + chunk)
            m = core & (h <= DASH["max_h"]) & (w >= DASH["min_w"]) & (w <= DASH["max_w"])
            if tree is not None and m.any():
                dist, _ = tree.query(np.c_[cx[m], cy[m]])
                m[np.flatnonzero(m)[dist <= DASH["tuft_base_m"]]] = False
            r, c = cy[m] // CELL, cx[m] // CELL
            ok = (r < n_r) & (c < n_c)
            np.add.at(g, (r[ok], c[ok]), 1)
            total += int(ok.sum())
            r5, c5 = cy[m] // f, cx[m] // f
            ok5 = (r5 < g5.shape[0]) & (c5 < g5.shape[1])
            np.add.at(g5, (r5[ok5], c5[ok5]), 1)
            long_ids = np.flatnonzero(np.maximum(h, w) > DASH["field_line_m"]) + 1
            if len(long_ids):
                core_lab = lab[y0 - ya: min(y0 + chunk, height) - ya, x0 - xa: min(x0 + chunk, width) - xa]
                lines = np.isin(core_lab, long_ids)
                hh, ww = lines.shape[0] // f * f, lines.shape[1] // f * f
                blk = lines[:hh, :ww].reshape(hh // f, f, ww // f, f).any(axis=(1, 3))
                line5[y0 // f: y0 // f + blk.shape[0], x0 // f: x0 // f + blk.shape[1]] |= blk
    return nd.uniform_filter(g, DASH["window"], mode="nearest"), total, g5, line5


def field_density(window, g5, line5, n_r, n_c):
    """Dash density per field enclosed by the map's own field lines."""
    f = DASH["field_res"]
    barrier = nd.binary_dilation(line5, iterations=1)
    lab, n = nd.label(~barrier)
    cells = np.bincount(lab.ravel(), minlength=n + 1).astype(float)
    dashes = np.bincount(lab.ravel(), weights=g5.ravel(), minlength=n + 1)
    per_cell = (CELL // f) ** 2
    dens = np.where(cells > 0, dashes / np.maximum(cells, 1) * per_cell, np.nan)
    ha = cells * f * f / 1e4
    dens[(ha < DASH["field_min_ha"]) | (ha > DASH["field_max_ha"])] = np.nan
    dens[0] = np.nan
    d5 = dens[lab]
    k = CELL // f
    d5 = d5[: n_r * k, : n_c * k]
    pad_r, pad_c = n_r * k - d5.shape[0], n_c * k - d5.shape[1]
    if pad_r or pad_c:
        d5 = np.pad(d5, ((0, pad_r), (0, pad_c)), constant_values=np.nan)
    blocks = d5.reshape(n_r, k, n_c, k)
    with np.errstate(invalid="ignore"):
        cnt = np.isfinite(blocks).sum(axis=(1, 3))
        val = np.nansum(blocks, axis=(1, 3)) / np.maximum(cnt, 1)
    return np.where(cnt > 0, val, window)


def count_grid(cols, rows, n_r, n_c):
    """Detections per 25 m cell (cols/rows in pixel coordinates of the 1 m map)."""
    g = np.zeros((n_r, n_c))
    r, c = (np.asarray(rows) // CELL).astype(int), (np.asarray(cols) // CELL).astype(int)
    ok = (r >= 0) & (r < n_r) & (c >= 0) & (c < n_c)
    np.add.at(g, (r[ok], c[ok]), 1)
    return g


def torf_layers(torf, min_chains, near_cells):
    k = TORF_RECUR_CELLS
    n = np.rint(nd.uniform_filter(torf.astype(float), k, mode="constant") * k * k)
    recurring = (n >= min_chains) & (torf > 0)
    torf_moor = nd.binary_dilation(recurring, structure=np.ones((near_cells, near_cells)))
    return recurring, torf_moor


def majority(a):
    k = np.ones((3, 3), int)
    counts = np.stack([nd.convolve((a == c).astype(int), k, mode="nearest") for c in range(4)])
    return counts.argmax(axis=0).astype(int)


def classify(tuft_w, dash, torf_moor, t_min, d_min, t_heath=None):
    """t_heath: tufts per 75 m needed for Heide (default t_min). Raising it removes
    the small 'heath' squares that single false tufts make in dry meadow."""
    out = np.zeros(tuft_w.shape, int)
    wet = dash >= d_min
    out[wet] = 2
    out[(tuft_w >= (t_heath or t_min)) & ~wet] = 3
    out[(tuft_w >= t_min) & wet] = 1
    out[torf_moor] = 1
    return majority(out)


def heath_in_moor(p, recurring, r_cells):
    near = nd.binary_dilation(recurring, structure=np.ones((r_cells, r_cells)))
    hl, hn = nd.label(p == 3)
    ml, _ = nd.label(p == 1)
    out = p.copy()
    if hn == 0:
        return out
    m_size = np.bincount(ml.ravel())
    h_size = np.bincount(hl.ravel())
    touch = nd.grey_dilation(ml, size=3)
    near_hit = set(np.unique(hl[near & (hl > 0)]))
    for i in range(1, hn + 1):
        cells = hl == i
        if i in near_hit:
            out[cells] = 1
            continue
        t = np.unique(touch[cells])
        t = t[t > 0]
        if len(t) and m_size[t].sum() >= h_size[i]:
            out[cells] = 1
    return out


def classes(band, width, height, tufts, torfs, P, feedback=None, t_heath=None):
    """Full chain: returns the class grid (0 none, 1 Moor, 2 nasse Wiese, 3 Heide)
    on a 25 m grid aligned with the map's top-left corner.
    tufts / torfs: arrays of (col, row) pixel positions."""
    n_r, n_c = height // CELL, width // CELL
    res = dash_density(band, width, height, n_r, n_c, tufts, feedback=feedback)
    if res is None:
        return None
    dash_w, _, g5, line5 = res
    dash = field_density(dash_w, g5, line5, n_r, n_c) if P.get("dash_mode") == "field" else dash_w
    tuft = count_grid(tufts[:, 0], tufts[:, 1], n_r, n_c) if len(tufts) else np.zeros((n_r, n_c))
    tuft_w = nd.uniform_filter(tuft, 3, mode="constant") * 9
    torf = count_grid(torfs[:, 0], torfs[:, 1], n_r, n_c) if len(torfs) else np.zeros((n_r, n_c))
    recurring, torf_moor = torf_layers(torf, P["torf_min"], P["torf_near"])
    return heath_in_moor(classify(tuft_w, dash, torf_moor, P["t_min"], P["d_min"], t_heath),
                         recurring, P["r_heath"])
