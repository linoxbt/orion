"""The operator's view of the whole protocol.

The backend's root used to answer JSON to a browser, which is useless to the
person actually running this. This serves a real dashboard instead: what is
connected, what it is doing, what it has earned, and what needs attention.

Gated by the same admin key as every other privileged route, but through a
sign-in form and an HttpOnly cookie rather than a header, because a browser
cannot set a header by navigating. The key never appears in a URL: putting it
in a query string would write it into every access log and referrer between
here and the operator's machine.
"""

import hmac
import logging
from typing import Any

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.services import admin_stats

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

COOKIE = "orion_admin"
# Long-lived on purpose: this is an operator's own machine, and being asked
# to paste a key every working day trains the habit of keeping it somewhere
# convenient and unsafe. Not unbounded, though - a session that never expires
# is one a stolen laptop keeps forever. Signing out revokes it immediately.
COOKIE_MAX_AGE = 30 * 24 * 3600


def _authorised(request: Request) -> bool:
    token = request.cookies.get(COOKIE)
    if not token or not settings.admin_api_key:
        return False
    # Constant time: a fast reject leaks how much of the key was right.
    return hmac.compare_digest(token, settings.admin_api_key)


# ---- rendering -------------------------------------------------------------

def _esc(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


STYLE = """
:root{--bg:#0d0e10;--surface:#15171a;--surface2:#1c1f23;--line:#26292e;
--line2:#3a3e45;--ink:#f2f0ed;--muted:#8b9098;--accent:#fc6432;
--good:#5fbf94;--warn:#d9a441;--bad:#e0685a;
--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif;
-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 72px}
header.top{display:flex;flex-wrap:wrap;gap:14px;align-items:baseline;
justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:20px}
.brand{display:flex;align-items:center;gap:9px;font-size:19px;font-weight:600;
letter-spacing:-.02em}
.brand i{width:9px;height:9px;background:var(--accent);
transform:rotate(45deg);display:inline-block}
.stamp{font-family:var(--mono);font-size:11px;color:var(--muted)}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.18em;
color:var(--muted);font-family:var(--mono);font-weight:500;margin:38px 0 14px}
.grid{display:grid;gap:14px}
.g4{grid-template-columns:repeat(4,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g2{grid-template-columns:repeat(2,1fr)}
@media(max-width:900px){.g4,.g3{grid-template-columns:repeat(2,1fr)}
.g2{grid-template-columns:1fr}}
@media(max-width:520px){.g4,.g3{grid-template-columns:1fr}}
.tile{background:var(--surface);border:1px solid var(--line);
border-radius:9px;padding:18px}
.tile .n{font-size:30px;font-weight:600;letter-spacing:-.02em;
font-variant-numeric:tabular-nums}
.tile .l{margin-top:6px;font-size:13px;color:var(--muted);line-height:1.4}
.tile .n.accent{color:var(--accent)}
.tile .n.good{color:var(--good)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
.scroll{overflow-x:auto;background:var(--surface);border:1px solid var(--line);
border-radius:9px}
th{text-align:left;font-weight:500;color:var(--muted);font-size:11px;
text-transform:uppercase;letter-spacing:.14em;font-family:var(--mono);
padding:12px 16px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:12px 16px;border-bottom:1px solid var(--line);white-space:nowrap}
tr:last-child td{border-bottom:0}
.mono{font-family:var(--mono);font-size:12px;color:var(--muted)}
.pill{display:inline-block;padding:3px 9px;border-radius:99px;font-size:11px;
font-family:var(--mono);letter-spacing:.06em;border:1px solid var(--line2)}
.pill.good{color:var(--good);border-color:#2c4a3d;background:#12211b}
.pill.warn{color:var(--warn);border-color:#4a3f22;background:#1f1a10}
.pill.bad{color:var(--bad);border-color:#4a2b27;background:#211311}
.pill.idle{color:var(--muted)}
.row{display:flex;align-items:center;justify-content:space-between;gap:14px;
padding:13px 16px;border-bottom:1px solid var(--line)}
.row:last-child{border-bottom:0}
.row .name{font-weight:500}
.row .det{font-size:12.5px;color:var(--muted);margin-top:2px}
.bar{height:6px;border-radius:99px;background:var(--surface2);overflow:hidden;
margin-top:10px}
.bar i{display:block;height:100%;background:var(--accent);border-radius:99px}
.empty{padding:26px 16px;color:var(--muted);font-size:14px}
form.login{max-width:340px;margin:14vh auto;background:var(--surface);
border:1px solid var(--line);border-radius:10px;padding:26px}
input{width:100%;margin-top:14px;padding:11px 13px;border-radius:7px;
border:1px solid var(--line2);background:var(--bg);color:var(--ink);font-size:14px}
button{width:100%;margin-top:14px;padding:11px;border-radius:7px;border:0;
background:var(--accent);color:#131416;font-weight:600;font-size:14px;cursor:pointer}
.err{margin-top:12px;color:var(--bad);font-size:13px}
footer{margin-top:44px;border-top:1px solid var(--line);padding-top:18px;
display:flex;flex-wrap:wrap;gap:12px;justify-content:space-between;
font-size:12px;color:var(--muted)}
"""


def _page(body: str, title: str = "Orion control") -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html lang=en><head><meta charset=utf-8>"
        f"<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{_esc(title)}</title><style>{STYLE}</style></head>"
        f"<body>{body}</body></html>"
    )


def _state(ok: bool | None, on: str, off: str, unknown: str = "unknown") -> str:
    if ok is None:
        return f'<span class="pill idle">{unknown}</span>'
    cls, text = ("good", on) if ok else ("bad", off)
    return f'<span class="pill {cls}">{text}</span>'


STATUS_PILL = {
    "completed": "good",
    "calling": "warn",
    "pending": "idle",
    "failed": "bad",
    "success": "good",
    "abandoned": "idle",
    "reversal-pending": "warn",
    "failed_payment": "bad",
}


def _render(d: dict[str, Any]) -> str:
    acc, neg, pay = d["accounts"], d["negotiations"], d["payments"]

    out = [
        '<div class="wrap"><header class="top">',
        '<div class="brand"><i></i>Orion control</div>',
        f'<div class="stamp">{_esc(d["generated_at"])} &middot; '
        f'<a href="/admin">refresh</a> &middot; <a href="/admin/logout">sign out</a></div>',
        "</header>",
    ]

    # What is running.
    out.append("<h2>Protocol</h2><div class='grid g4'>")
    live = neg["by_status"].get("calling", 0)
    out += [
        f'<div class="tile"><div class="n">{neg["total"]}</div>'
        f'<div class="l">Negotiations, excluding {neg["samples"]} seeded examples</div></div>',
        f'<div class="tile"><div class="n{" accent" if live else ""}">{live}</div>'
        '<div class="l">Calls live right now</div></div>',
        f'<div class="tile"><div class="n good">{neg["verified"]}</div>'
        '<div class="l">Verified from a call recording</div></div>',
        f'<div class="tile"><div class="n">{acc["total"]}</div>'
        f'<div class="l">Accounts, {acc["pro"]} on a paid plan</div></div>',
    ]
    out.append("</div>")

    # Money.
    settled = f'{pay["settled"]:,.2f}' if pay else "-"
    cur = pay["currency"] if pay else ""
    out.append("<h2>Money</h2><div class='grid g4'>")
    out += [
        f'<div class="tile"><div class="n good">${neg["monthly_saving"]:,.2f}</div>'
        '<div class="l">Monthly saving found, verified only</div></div>',
        f'<div class="tile"><div class="n">{cur} {settled}</div>'
        '<div class="l">Settled in the last 25 transactions</div></div>',
        f'<div class="tile"><div class="n">{acc["bills_used_this_month"]}</div>'
        f'<div class="l">Bills used in {acc["month"]}, {acc["free_allowance"]} free per account</div></div>',
        f'<div class="tile"><div class="n">{neg["with_recording"]}</div>'
        '<div class="l">Calls with a stored recording</div></div>',
    ]
    out.append("</div>")

    # Integrations.
    out.append("<h2>Integrations</h2><div class='scroll'>")
    for name, meta in d["integrations"].items():
        if not meta["configured"]:
            pill = '<span class="pill idle">not configured</span>'
        else:
            pill = _state(meta["reachable"], "live", "unreachable", "configured")
        out.append(
            f'<div class="row"><div><div class="name">{_esc(name)}</div>'
            f'<div class="det">{_esc(meta["detail"])}</div></div>{pill}</div>'
        )
    out.append("</div>")

    # Negotiations.
    out.append("<h2>Recent negotiations</h2><div class='scroll'>")
    if neg["recent"]:
        out.append(
            "<table><thead><tr><th>Provider</th><th>Status</th><th>Verified</th>"
            "<th>Recording</th><th>Outcome</th><th>Account</th></tr></thead><tbody>"
        )
        for n in neg["recent"]:
            cls = STATUS_PILL.get(n["status"], "idle")
            out.append(
                f'<tr><td>{_esc(n["provider"])}</td>'
                f'<td><span class="pill {cls}">{_esc(n["status"])}</span></td>'
                f'<td>{"yes" if n["verified"] else "&mdash;"}</td>'
                f'<td>{"stored" if n["recording"] else "&mdash;"}</td>'
                f'<td class="mono">{_esc(n["outcome"]) or "&mdash;"}</td>'
                f'<td class="mono">{_esc((n["user_id"] or "")[:12])}</td></tr>'
            )
        out.append("</tbody></table>")
    else:
        out.append('<div class="empty">No negotiations yet.</div>')
    out.append("</div>")

    # Payments, verbatim.
    out.append("<h2>Payments</h2><div class='scroll'>")
    if pay and pay["recent"]:
        out.append(
            "<table><thead><tr><th>When</th><th>Status</th><th>Amount</th>"
            "<th>Channel</th><th>Account</th><th>Reference</th></tr></thead><tbody>"
        )
        for t in pay["recent"]:
            cls = STATUS_PILL.get(t["status"], "idle")
            out.append(
                f'<tr><td class="mono">{_esc(t["at"])}</td>'
                f'<td><span class="pill {cls}">{_esc(t["status"])}</span></td>'
                f'<td>{_esc(t["currency"])} {t["amount"]:,.2f}</td>'
                f'<td>{_esc(t["channel"] or "&mdash;")}</td>'
                f'<td class="mono">{_esc((t["user_id"] or "")[:12]) or "&mdash;"}</td>'
                f'<td class="mono">{_esc(t["reference"])}</td></tr>'
            )
        out.append("</tbody></table>")
    elif pay is None:
        out.append('<div class="empty">Payments are not connected on this deployment.</div>')
    else:
        out.append('<div class="empty">No transactions yet.</div>')
    out.append("</div>")

    # Breakdowns.
    out.append("<h2>Breakdown</h2><div class='grid g2'>")
    for heading, data in (("By status", neg["by_status"]),
                          ("By provider", neg["providers"])):
        rows = "".join(
            f'<div class="row"><div class="name">{_esc(k)}</div>'
            f'<div class="mono">{v}</div></div>'
            for k, v in data.items()
        ) or '<div class="empty">Nothing yet.</div>'
        out.append(f'<div class="scroll"><div class="row"><div class="name">'
                   f'{heading}</div></div>{rows}</div>')
    out.append("</div>")

    out.append(
        '<footer><span>Orion protocol control. Every figure is read live; '
        'nothing here is estimated.</span>'
        '<span><a href="https://app.useorion.xyz">application</a> &middot; '
        '<a href="/docs">API reference</a></span></footer></div>'
    )
    return "".join(out)


# ---- routes ----------------------------------------------------------------

@router.get("/", include_in_schema=False)
async def root(request: Request):
    return RedirectResponse("/admin", status_code=307)


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request):
    if not _authorised(request):
        return _page(
            '<form class="login" method="post" action="/admin/login">'
            '<div class="brand"><i></i>Orion control</div>'
            '<input type="password" name="key" placeholder="Admin key" autofocus '
            'autocomplete="current-password" required>'
            "<button type=submit>Sign in</button></form>",
            "Orion control",
        )

    try:
        data = await admin_stats.collect()
    except Exception as exc:  # noqa: BLE001 - a dashboard must not 500
        logger.exception("Dashboard could not be assembled")
        return _page(
            f'<div class="wrap"><h2>Something did not load</h2>'
            f'<div class="scroll"><div class="empty">{_esc(exc)}</div></div></div>'
        )
    return _page(_render(data))


@router.post("/admin/login", include_in_schema=False)
async def login(response: Response, key: str = Form(...)):
    if not settings.admin_api_key or not hmac.compare_digest(key, settings.admin_api_key):
        return _page(
            '<form class="login" method="post" action="/admin/login">'
            '<div class="brand"><i></i>Orion control</div>'
            '<input type="password" name="key" placeholder="Admin key" autofocus '
            'autocomplete="current-password" required>'
            '<button type=submit>Sign in</button>'
            '<p class="err">That key was not accepted.</p></form>',
            "Orion control",
        )

    redirect = RedirectResponse("/admin", status_code=303)
    # HttpOnly so no script can read it, Secure so it never crosses plain HTTP,
    # SameSite=lax so another site cannot navigate a browser into using it.
    redirect.set_cookie(
        COOKIE,
        settings.admin_api_key,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return redirect


@router.get("/admin/logout", include_in_schema=False)
async def logout():
    redirect = RedirectResponse("/admin", status_code=303)
    redirect.delete_cookie(COOKIE)
    return redirect
