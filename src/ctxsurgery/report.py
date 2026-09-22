"""Self-contained, script-free HTML evidence reports."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
import math
from typing import Any


def _text(value: Any) -> str:
    return escape(str(value), quote=True)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def _items(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _mapping(value: Any) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def render_html(result: Mapping) -> str:
    """Render JSON diagnostic evidence without scripts, assets or network access.

    All report content is untrusted and escaped. CSS dimensions are derived only
    from finite, clamped numeric values. This does not redact sensitive evidence.
    """
    if not isinstance(result, Mapping):
        raise TypeError("result must be a mapping")

    name = _text(result.get("case_name", "Untitled case"))
    status = str(result.get("status", "inconclusive"))
    tone = "success" if status == "localized" else "warning"
    summary = _text(result.get("summary", "No summary was recorded."))
    repair_ids = [str(value) for value in _items(result.get("repair_ids"))]
    experiments = [_mapping(value) for value in _items(result.get("experiments"))]
    anchors = {str(exp.get("id", "")): f"experiment-{i}" for i, exp in enumerate(experiments)}
    run = _mapping(result.get("run"))
    if run.get("synthetic") is True:
        provenance = "Synthetic · deterministic demo"
        provenance_detail = (
            "These results come from a synthetic deterministic runner, not measured LLM behavior. "
            "Use this report to inspect the method and interface, not to infer model reliability."
        )
    elif run.get("synthetic") is False:
        provenance = "Live · user-selected runner"
        provenance_detail = (
            "Provider and model were selected by the user. These are observations from this run, "
            "not a statistical or universal causal guarantee."
        )
    else:
        provenance = "Execution provenance not recorded"
        provenance_detail = "This report does not establish whether a live model or a synthetic runner was used."

    repair_html = "".join(f'<span class="fragment-id">{_text(value)}</span>' for value in repair_ids)
    if not repair_html:
        repair_html = '<span class="muted">No supported repair identified</span>'
    minimality = str(result.get("minimality", "not-established"))
    minimality_detail = (
        "No single retained fragment can be removed while preserving the tested repair criterion. "
        "This is an ordered greedy, 1-minimal result—not a globally smallest repair."
        if minimality == "1-minimal"
        else "Minimality was not established. Do not interpret the displayed fragment set as a minimal repair."
    )

    experiment_rows = []
    experiment_details = []
    for i, exp in enumerate(experiments):
        kind = str(exp.get("kind", "unknown"))
        kind_class = kind if kind in {"before", "after", "restore", "filler"} else "unknown"
        valid = exp.get("valid") is True
        rate = min(1.0, max(0.0, _number(exp.get("pass_rate"))))
        rate_label = f"{rate:.0%}" if valid else "Invalid"
        fragments = ", ".join(str(value) for value in _items(exp.get("fragment_ids"))) or "—"
        trials = [_mapping(value) for value in _items(exp.get("trials"))]
        passing = sum(trial.get("passed") is True for trial in trials)
        errors = sum(trial.get("error") is not None for trial in trials)
        exp_id = _text(exp.get("id", str(i)))
        experiment_rows.append(
            f'<tr><td><a href="#experiment-{i}">{exp_id}</a>'
            f'<span class="kind {kind_class}">{_text(kind)}</span></td>'
            f'<td class="mono">{_text(fragments)}</td>'
            f'<td class="number">{int(max(0, _number(exp.get("context_chars")))):,}</td>'
            f'<td><div class="rate"><div class="track"><span style="width:{rate * 100 if valid else 0:.2f}%"></span></div>'
            f'<strong>{rate_label}</strong></div>'
            f'<small>{passing}/{len(trials)} passed · {errors} errors</small></td></tr>'
        )
        trial_html = []
        for trial in trials:
            has_error = trial.get("error") is not None
            passed = trial.get("passed")
            label = "ERROR · not evidence" if has_error else ("PASS" if passed is True else "FAIL" if passed is False else "NOT SCORED")
            content = trial.get("error") if has_error else trial.get("output")
            content = "No output recorded" if content is None else content
            trial_html.append(
                '<div class="trial">'
                f'<div class="trial-heading"><strong>{label}</strong>'
                f'<span>Trial {_text(trial.get("index", "?"))} · {_number(trial.get("elapsed_ms")):.1f} ms</span></div>'
                f'<pre>{_text(content)}</pre></div>'
            )
        experiment_details.append(
            f'<details id="experiment-{i}"><summary><span>{exp_id} <span class="kind {kind_class}">{_text(kind)}</span></span>'
            f'<span>{rate_label} · {len(trials)} trials</span></summary>'
            f'<div class="detail-body">{"".join(trial_html) or "<p>No trials recorded.</p>"}</div></details>'
        )

    def experiment_link(value: Any) -> str:
        if value is None:
            return "—"
        label = _text(value)
        anchor = anchors.get(str(value))
        return f'<a href="#{anchor}">{label}</a>' if anchor else label

    check_rows = []
    for raw_check in _items(result.get("checks")):
        check = _mapping(raw_check)
        survives = check.get("repair_survives")
        outcome = "Repair survives" if survives is True else "Repair breaks" if survives is False else "Undetermined"
        check_rows.append(
            f'<tr><td class="mono">{_text(check.get("removed_id", "?"))}</td>'
            f'<td>{experiment_link(check.get("restore_experiment"))}</td>'
            f'<td>{experiment_link(check.get("filler_experiment"))}</td><td>{outcome}</td></tr>'
        )
    checks_html = (
        '<div class="table-wrap"><table><thead><tr><th>Remove fragment</th><th>Restoration</th><th>Filler control</th><th>Observed result</th></tr></thead>'
        f'<tbody>{"".join(check_rows)}</tbody></table></div>'
        if check_rows else '<p class="muted">No leave-one-out checks were recorded.</p>'
    )
    candidate_html = []
    for raw_candidate in _items(result.get("candidates")):
        candidate = _mapping(raw_candidate)
        fragment_id = str(candidate.get("id", "?"))
        retained = fragment_id in repair_ids
        candidate_html.append(
            f'<article class="candidate{" selected" if retained else ""}">'
            f'<div class="candidate-heading"><code>{_text(fragment_id)}</code>'
            f'<span>{"In proposed repair" if retained else "Candidate"}</span></div>'
            f'<pre>{_text(candidate.get("text", ""))}</pre></article>'
        )
    limitations = [str(value) for value in _items(result.get("limitations"))]
    if not limitations:
        limitations = ["No run-specific limitations were recorded. This is not evidence that the experiment has none."]
    limitation_html = "".join(f"<li>{_text(value)}</li>" for value in limitations)
    provider = _text(run.get("provider", "Not recorded"))
    model = _text(run.get("model", "Not recorded"))
    calls = int(max(0, _number(result.get("calls_used"))))
    max_calls = int(max(0, _number(result.get("max_calls"))))
    repeats = int(max(0, _number(result.get("repeats"))))
    threshold = min(1.0, max(0.0, _number(result.get("pass_threshold"), 1.0)))
    elapsed = _number(result.get("elapsed_ms")) / 1000
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{name} — ctxsurgery evidence report</title>
<style>
:root{{--paper:#f5f3ed;--panel:#fffefa;--ink:#172c35;--muted:#59686b;--line:#d3d8d3;--teal:#086859;--blue:#245e93;--amber:#76531a;--faint:#e8eee9}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:Georgia,'Times New Roman',serif;line-height:1.55}}a{{color:var(--blue);text-underline-offset:3px}}a:hover{{text-decoration-thickness:2px}}a:focus-visible,summary:focus-visible{{outline:3px solid var(--blue);outline-offset:4px}}.shell{{max-width:1190px;margin:auto;padding:35px 46px 70px}}.masthead{{display:flex;justify-content:space-between;gap:20px;border-bottom:2px solid var(--ink);padding:0 0 18px;font-family:'Courier New',monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase}}.brand{{font-size:18px;font-weight:bold;letter-spacing:-.04em}}.hero{{padding:43px 0 29px;display:grid;grid-template-columns:1fr 280px;gap:44px}}.eyebrow,.section-number,.label{{font-family:'Courier New',monospace;font-size:11px;letter-spacing:.13em;text-transform:uppercase}}.eyebrow{{color:var(--teal);font-weight:bold}}h1{{font-size:clamp(32px,4.8vw,54px);line-height:1.1;font-weight:normal;letter-spacing:-.035em;margin:12px 0 18px;overflow-wrap:anywhere}}.lede{{font-size:18px;max-width:720px;margin:16px 0}}.badge{{display:inline-block;padding:5px 10px;border:1px solid;font:12px 'Courier New',monospace;overflow-wrap:anywhere}}.success{{color:var(--teal);background:#e6f1e9}}.warning{{color:var(--amber);background:#f5eedf}}.run-card{{border-left:1px solid var(--line);padding-left:25px;align-self:start;font-size:13px}}.run-card strong{{font-size:15px;display:block;line-height:1.4;margin-bottom:12px}}.run-card p{{color:var(--muted)}}.run-card dl{{display:grid;grid-template-columns:65px 1fr;gap:6px 12px;font-family:'Courier New',monospace;font-size:11px}}dt{{color:var(--muted)}}dd{{margin:0;overflow-wrap:anywhere}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-bottom:34px}}.metric{{padding:15px 18px 17px 0}}.metric+.metric{{padding-left:20px;border-left:1px solid var(--line)}}.metric .value{{display:block;font-size:27px;margin-top:3px}}.metric small{{font-size:14px;color:var(--muted)}}section{{margin-top:38px}}.section-head{{display:flex;align-items:baseline;gap:14px;margin-bottom:12px}}.section-number{{color:var(--teal)}}h2{{font-size:25px;font-weight:normal;letter-spacing:-.02em;margin:0}}.section-note{{color:var(--muted);font-size:14px;margin:7px 0 17px;max-width:840px}}.repair-box{{padding:21px 24px;border:1px solid var(--line);border-left:4px solid var(--teal);background:var(--panel)}}.repair-box p{{margin:13px 0 0;font-size:14px;color:var(--muted)}}.fragment-id{{display:inline-block;font:14px 'Courier New',monospace;padding:5px 9px;margin:0 8px 6px 0;background:var(--faint);overflow-wrap:anywhere}}.minimality{{font:11px 'Courier New',monospace;text-transform:uppercase;letter-spacing:.06em}}.table-wrap{{overflow-x:auto;border:1px solid var(--line);background:var(--panel)}}table{{width:100%;border-collapse:collapse;font-size:14px;text-align:left}}th{{font:10px 'Courier New',monospace;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);padding:13px 18px;background:#eef0e9}}td{{padding:14px 18px;border-top:1px solid var(--line);vertical-align:top}}td:first-child>a{{font-family:'Courier New',monospace}}.kind{{display:inline-block;font:10px 'Courier New',monospace;text-transform:uppercase;color:var(--muted);margin-left:10px;letter-spacing:.03em}}.restore{{color:var(--teal)}}.filler{{color:var(--amber)}}.mono,code{{font-family:'Courier New',monospace;overflow-wrap:anywhere}}.number{{font-family:'Courier New',monospace;text-align:right;white-space:nowrap}}.rate{{display:flex;align-items:center;gap:10px;min-width:150px}}.rate strong{{font:12px 'Courier New',monospace;min-width:42px}}.track{{width:85px;height:7px;background:#e5e9e3}}.track span{{height:100%;display:block;background:var(--teal)}}td small{{display:block;color:var(--muted);font-size:11px;margin-top:5px}}.candidate-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.candidate{{background:var(--panel);border:1px solid var(--line);padding:16px 18px;min-width:0}}.candidate.selected{{border-left:4px solid var(--teal);padding-left:15px}}.candidate-heading,.trial-heading{{display:flex;justify-content:space-between;gap:12px;font:11px 'Courier New',monospace}}.candidate-heading span{{color:var(--muted)}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.65 'Courier New',monospace;margin:14px 0 0}}details{{border:1px solid var(--line);background:var(--panel);margin:8px 0;scroll-margin-top:18px}}summary{{cursor:pointer;padding:13px 18px;font:12px 'Courier New',monospace;display:flex;justify-content:space-between;gap:18px}}summary::before{{content:'+';color:var(--teal);font-weight:bold;margin-right:8px}}details[open]>summary::before{{content:'−'}}summary>span:first-of-type{{flex:1}}details[open]>summary{{border-bottom:1px solid var(--line)}}.detail-body{{padding:0 18px}}.trial{{padding:16px 0}}.trial+.trial{{border-top:1px dashed var(--line)}}.trial-heading span{{color:var(--muted)}}.limitations{{border-top:2px solid var(--ink);padding-top:22px}}.limitations li{{font-size:14px;margin:8px 0;padding-left:4px}}.limitations ul{{padding-left:20px}}.muted{{color:var(--muted)}}footer{{margin-top:42px;padding-top:18px;border-top:1px solid var(--line);font:10px/1.8 'Courier New',monospace;color:var(--muted);display:flex;justify-content:space-between;gap:30px}}footer p{{margin:0;max-width:620px}}@media(max-width:760px){{.shell{{padding:22px 18px 40px}}.hero{{grid-template-columns:1fr;gap:20px;padding-top:27px}}.run-card{{border-left:0;border-top:1px solid var(--line);padding:18px 0 0}}.metrics{{grid-template-columns:1fr 1fr}}.metric:nth-child(3){{border-left:0;padding-left:0;border-top:1px solid var(--line)}}.metric:nth-child(4){{border-top:1px solid var(--line)}}.candidate-grid{{grid-template-columns:1fr}}td,th{{padding:11px 12px}}.masthead{{align-items:center;font-size:9px}}footer{{display:block}}footer p+p{{margin-top:12px}}summary{{flex-wrap:wrap}}}}@media print{{body{{background:white}}.shell{{max-width:none;padding:0}}.hero{{padding-top:24px}}details{{break-inside:avoid}}.candidate{{break-inside:avoid}}.table-wrap{{overflow:visible}}a{{color:inherit}}.rate{{min-width:0}}}}
</style></head><body><main class="shell">
<header class="masthead"><span class="brand">ctxsurgery /</span><span>Context restoration · evidence report</span></header>
<div class="hero"><div><div class="eyebrow">Debug the missing context</div><h1>{name}</h1><span class="badge {tone}">{_text(status)}</span><p class="lede">{summary}</p></div>
<aside class="run-card" aria-label="Run provenance"><strong>{_text(provenance)}</strong><p>{_text(provenance_detail)}</p><dl><dt>Provider</dt><dd>{provider}</dd><dt>Model</dt><dd>{model}</dd></dl></aside></div>
<div class="metrics" aria-label="Experiment settings"><div class="metric"><span class="label">Runner calls</span><span class="value">{calls}<small> / {max_calls}</small></span></div><div class="metric"><span class="label">Trials per arm</span><span class="value">{repeats}</span></div><div class="metric"><span class="label">Pass threshold</span><span class="value">{threshold:.0%}</span></div><div class="metric"><span class="label">Elapsed</span><span class="value">{elapsed:.2f}<small> s</small></span></div></div>
<section aria-labelledby="repair-title"><div class="section-head"><span class="section-number">01</span><h2 id="repair-title">Proposed repair</h2></div><div class="repair-box"><div>{repair_html}</div><p><span class="minimality">{_text(minimality)}</span> · {_text(minimality_detail)}</p></div></section>
<section aria-labelledby="experiments-title"><div class="section-head"><span class="section-number">02</span><h2 id="experiments-title">Controlled experiments</h2></div><p class="section-note">Original and reduced contexts establish the comparison. Restore adds candidate fragments; filler adds character-matched neutral text. Errors invalidate evidence rather than count as a task failure.</p><div class="table-wrap"><table><thead><tr><th>Experiment / arm</th><th>Fragment IDs</th><th class="number">Context chars</th><th>Observed pass rate</th></tr></thead><tbody>{"".join(experiment_rows) or '<tr><td colspan="4">No experiments recorded.</td></tr>'}</tbody></table></div></section>
<section aria-labelledby="checks-title"><div class="section-head"><span class="section-number">03</span><h2 id="checks-title">Leave-one-out evidence</h2></div><p class="section-note">Each check asks whether a proposed repair survives without one fragment. The search order can affect the result.</p>{checks_html}</section>
<section aria-labelledby="fragments-title"><div class="section-head"><span class="section-number">04</span><h2 id="fragments-title">Candidate fragments</h2></div><p class="section-note">Detected by whitespace-normalized exact substring matching, not semantic understanding. A paraphrase can appear as a missing fragment.</p><div class="candidate-grid">{"".join(candidate_html) or '<p class="muted">No missing-fragment candidates recorded.</p>'}</div></section>
<section aria-labelledby="trials-title"><div class="section-head"><span class="section-number">05</span><h2 id="trials-title">Trial ledger</h2></div><p class="section-note">Expand an experiment to inspect the actual output or error for each fresh runner call.</p>{"".join(experiment_details) or '<p class="muted">No trial evidence recorded.</p>'}</section>
<section class="limitations" aria-labelledby="limits-title"><div class="section-head"><span class="section-number">06</span><h2 id="limits-title">What this establishes—and what it does not</h2></div><ul>{limitation_html}</ul><p class="section-note">Character-matched filler is not a token-matched placebo. Repeated observations are not a significance test, and 1-minimal is not globally minimum. Findings depend on the task, evaluator, runner, restoration position and sampled trials.</p></section>
<footer><p>ctxsurgery · local, self-contained report · schema {_text(result.get("schema_version", "unknown"))}<br>No scripts. No external assets. No report telemetry.</p><p>Privacy: this file can contain context fragments, model outputs and errors. Inspect or redact the JSON and HTML before sharing.</p></footer>
</main></body></html>'''
