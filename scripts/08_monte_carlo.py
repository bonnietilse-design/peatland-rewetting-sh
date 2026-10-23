"""
08 – Monte Carlo: how robust is the emission estimate?

The emission factors (Tiemeyer et al. 2020) come with 2.5–97.5 % percentiles
that describe how much single hectares differ (mainly water table). How much
that matters for the TOTAL of the test area depends on whether fields deviate
together or independently - which we don't know. So two bounding scenarios:

  whole_area  one random factor per land-use class for the whole AOI per run
              -> "the region as a whole could be wetter/drier than average"
              -> widest range (upper bound of uncertainty)
  per_parcel  an independent random factor for every Feldblock
              -> deviations largely cancel out over thousands of fields
              -> narrowest range (lower bound of uncertainty)

Distribution (config.MONTE_CARLO["distribution"]):
  skewed  two-piece normal in CO2-C space, fitted so that its mean equals the
          IEF (Table 5) and its 2.5/97.5 % quantiles match Table 2 (default)
  normal  symmetric mean ± sd in t CO2-eq (first version, for comparison)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from functools import lru_cache  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402
from scipy.stats import norm  # noqa: E402

import config as cfg  # noqa: E402
from peatsh.common import get_logger, read_layer, write_report  # noqa: E402

log = get_logger("08")
C_TO_CO2 = 44 / 12
SQRT_2_PI = np.sqrt(2 / np.pi)

# Physical floor for CO2-C per hectare [t C/ha/yr]. Drained land: the lower
# asymptote of the fitted Gompertz CO2 response function, CO2-Cmin = -0.93
# (Tiemeyer et al. 2020, p. 7) - even a fully wet field cannot go lower.
# Rewetted: lower 2.5 % value of Table 2 (-2.4). Without this floor the
# two-piece normal's tail produces impossible negative emissions.
CO2C_FLOOR = {"cropland": -0.93, "grassland": -0.93, "rewetted": -2.4}


def _tpn_quantile(p, mode, s1, s2):
    """Quantile of a two-piece normal (sd s1 left of the mode, s2 right)."""
    w = s1 / (s1 + s2)
    if p < w:
        return mode + s1 * norm.ppf(p * (s1 + s2) / (2 * s1))
    return mode + s2 * norm.ppf(1 - (1 - p) * (s1 + s2) / (2 * s2))


@lru_cache(maxsize=None)
def fit_two_piece(cls: str) -> tuple[float, float, float, float]:
    """Fit mode, s1, s2 [t C] so that the MEAN equals the CO2 part of the IEF
    (Table 5) and the 2.5 / 97.5 % quantiles match Table 2 (shifted by the
    same difference). Returns (mode, s1, s2, max fit error in t C)."""
    p = cfg._PAPER[cls]
    mean = p["co2c_ief"]
    t2_mean, lo, hi = p["co2c_t2"]
    lo, hi = lo + (mean - t2_mean), hi + (mean - t2_mean)

    def resid(x):
        m, s1, s2 = x
        # mean weighted ×100: it is the inventory value and must be kept;
        # the percentiles are matched as closely as the shape allows
        return [100 * (m + SQRT_2_PI * (s2 - s1) - mean),
                _tpn_quantile(0.025, m, s1, s2) - lo,
                _tpn_quantile(0.975, m, s1, s2) - hi]

    x0 = [mean, max((mean - lo) / 1.96, 0.01), max((hi - mean) / 1.96, 0.01)]
    res = least_squares(resid, x0, bounds=([-np.inf, 1e-3, 1e-3], [np.inf] * 3))
    m, s1, s2 = res.x
    q_err = max(abs(res.fun[1]), abs(res.fun[2]))   # percentile mismatch, t C
    return float(m), float(s1), float(s2), float(q_err)


def draw_ef(cls: str, size, rng: np.random.Generator, dist: str) -> np.ndarray:
    """Random emission factors [t CO2-eq/ha/yr] for one class."""
    ef = cfg.EMISSION_FACTORS[cls]
    if dist == "normal":
        return rng.normal(ef["mean"], ef["sd"], size)
    mode, s1, s2, _ = fit_two_piece(cls)
    left = rng.random(size) < s1 / (s1 + s2)
    dev = np.abs(rng.standard_normal(size))
    co2c = np.where(left, mode - dev * s1, mode + dev * s2)
    co2c = np.maximum(co2c, CO2C_FLOOR[cls])
    non_co2 = ef["mean"] - ef["co2c"] * C_TO_CO2   # CH4, N2O, DOC: fixed
    return co2c * C_TO_CO2 + non_co2


def run_whole_area(area: dict, n: int, rng, dist: str):
    rew = draw_ef("rewetted", n, rng, dist)
    total = np.zeros(n)
    saving = np.zeros(n)
    for c, a in area.items():
        d = draw_ef(c, n, rng, dist)
        total += a * d
        saving += a * (d - rew)
    return total, saving


def run_per_parcel(parcels, n: int, rng, dist: str, chunk: int = 500):
    """Independent draw per parcel; chunked to keep memory small."""
    total, saving = np.empty(n), np.empty(n)
    groups = {c: g.area_ha.to_numpy() for c, g in parcels.groupby("lu_class")}
    a_all = np.concatenate(list(groups.values()))
    for start in range(0, n, chunk):
        k = min(chunk, n - start)
        t = np.zeros(k)
        s = np.zeros(k)
        rew = draw_ef("rewetted", (k, a_all.size), rng, dist)
        col = 0
        for c, a in groups.items():
            d = draw_ef(c, (k, a.size), rng, dist)
            t += d @ a
            s += (d - rew[:, col:col + a.size]) @ a
            col += a.size
        total[start:start + k], saving[start:start + k] = t, s
    return total, saving


def pct(a):
    return np.percentile(a, [5, 50, 95])


def main() -> None:
    mc = cfg.MONTE_CARLO
    dist = mc.get("distribution", "skewed")
    n = mc["n_runs"]
    rng = np.random.default_rng(mc["seed"])

    em = read_layer("emissions")
    pid = cfg.FIELDS["parcel_id"]
    parcels = em.groupby([pid, "lu_class"], as_index=False).area_ha.sum()
    area = parcels.groupby("lu_class").area_ha.sum().to_dict()
    det = sum(a * cfg.EMISSION_FACTORS[c]["mean"] for c, a in area.items())

    log.info("whole_area scenario ...")
    t_w, s_w = run_whole_area(area, n, rng, dist)
    log.info("per_parcel scenario (%d parcels) ...", len(parcels))
    t_p, s_p = run_per_parcel(parcels, n, rng, dist)

    # --- figure -------------------------------------------------------------
    # Two panels with the SAME x-axis, so the widths are directly comparable;
    # each panel has its own y-axis (the per-parcel peak is ~30× taller).
    lo = min(t_w.min(), t_p.min()) / 1000
    hi = max(t_w.max(), t_p.max()) / 1000
    bins = np.linspace(lo, hi, 90)
    fig, axes = plt.subplots(2, 1, figsize=(8, 5.5), sharex=True)
    for ax, t, colour, title in (
        (axes[0], t_w, "#E69F00", "Whole area – all fields deviate together (upper bound)"),
        (axes[1], t_p, "#0072B2", "Per parcel – fields deviate independently (lower bound)"),
    ):
        p5, p50, p95 = pct(t) / 1000
        ax.hist(t / 1000, bins=bins, color=colour)
        ax.axvspan(p5, p95, color=colour, alpha=0.12, lw=0)
        ax.axvline(det / 1000, color="black", lw=1, ls="--")
        ax.set_title(f"{title}\nmedian {p50:,.0f} kt, 90 % range {p5:,.0f}–{p95:,.0f} kt",
                     fontsize=9, loc="left")
        ax.set_ylabel("Runs")
        ax.spines[["top", "right"]].set_visible(False)
    axes[1].set_xlabel("Total emissions, test area [kt CO2-eq/yr]   "
                       "(dashed: area × mean factor; shaded: 90 % range)")
    fig.suptitle(f"Monte Carlo, {n:,} runs – {dist} emission factors", fontsize=11)
    fig.tight_layout()
    png = cfg.OUTPUTS / f"08_monte_carlo_{cfg.aoi_label()}.png"
    fig.savefig(png, dpi=150)

    # --- report -------------------------------------------------------------
    def row(name, t, s):
        a, b = pct(t), pct(s)
        return (f"| {name} | {a[1]:,.0f} | {a[0]:,.0f} – {a[2]:,.0f} | "
                f"{b[1]:,.0f} | {b[0]:,.0f} – {b[2]:,.0f} |")

    ef_lines = ["| class | mean | per-hectare 2.5–97.5 % (drawn) | fit error |",
                "|---|---|---|---|"]
    for c, v in cfg.EMISSION_FACTORS.items():
        d = draw_ef(c, 200_000, np.random.default_rng(1), dist)
        lo, hi = np.percentile(d, [2.5, 97.5])
        err = f"{fit_two_piece(c)[3]:.2f} t C" if dist == "skewed" else "–"
        ef_lines.append(f"| {c} | {d.mean():.1f} | {lo:.1f} – {hi:.1f} | {err} |")
    write_report("08_monte_carlo", "Uncertainty of the emission estimate", [
        f"- runs: {n:,}, seed {mc['seed']}, distribution: **{dist}**",
        f"- deterministic estimate (area × mean factor): {det:,.0f} t CO2-eq/yr",
        f"- parcels in per-parcel scenario: {len(parcels):,}", "",
        "| scenario | emissions median | 90 % range | savings median | 90 % range |",
        "|---|---|---|---|---|",
        row("whole area (upper bound)", t_w, s_w),
        row("per parcel (lower bound)", t_p, s_p), "",
        "Emission factors drawn [t CO2-eq/ha/yr] (Tiemeyer et al. 2020: mean from",
        "Table 5, spread from the Table 2 percentiles). For drained land the",
        "distribution is lopsided: most hectares sit just below a ceiling (the CO2",
        "response levels off at deep drainage), with a long tail towards wetter,",
        "lower-emitting fields.", "", *ef_lines, "",
        "How to read this: the paper's ranges describe how much single hectares",
        "differ (mainly water table), not the uncertainty of an area average.",
        "If all fields in the test area deviated in the same direction (e.g. the",
        "whole region is wetter than the German average), the orange range applies.",
        "If fields deviated independently, errors cancel out (blue range). Reality",
        "lies in between, because neighbouring fields share ditches and pumping.",
        "Local water-table data would narrow this down.", "",
        "Not included: area/mapping errors, uncertainty of the response functions",
        "themselves, GWP choice (AR4).", "",
        f"![histogram](../../outputs/{png.name})",
    ])
    log.info("Report written")


if __name__ == "__main__":
    main()
