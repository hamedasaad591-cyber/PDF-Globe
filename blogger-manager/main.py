import os
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

APP_NAME = "Digital Content Gate Manager"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "hamedasaad591@gmail.com").strip().lower()
BLOG_URL = os.getenv("BLOG_URL", "https://digitalcontentgatehub.blogspot.com/").strip()
APP_BASE_URL = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(48)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
BLOGGER_API = "https://www.googleapis.com/blogger/v3"

# Tokens are held only in process memory. A restart/spin-down signs the user out,
# but never writes OAuth tokens to the repository or browser cookie.
USER_SESSIONS: dict[str, dict] = {}

app = FastAPI(title=APP_NAME)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="dcm_session",
    same_site="lax",
    https_only=True,
    max_age=60 * 60 * 8,
)

CSS = """
:root{color-scheme:light;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}
*{box-sizing:border-box}body{margin:0;background:#f4f6fb;color:#172033}
header{background:#14213d;color:#fff;padding:22px max(22px,calc((100% - 1080px)/2))}
header strong{font-size:18px}header small{display:block;color:#cbd5e1;margin-top:5px}
main{max-width:1080px;margin:34px auto;padding:0 20px}
.panel{background:#fff;border:1px solid #e3e8f1;border-radius:16px;padding:24px;margin-bottom:18px;box-shadow:0 8px 30px #15213d0a}
h1{font-size:26px;margin:0 0 10px}h2{font-size:19px;margin:0 0 14px}
p{line-height:1.65;color:#526078}.muted{color:#718096;font-size:13px}
a{color:#2457c5;text-decoration:none}a:hover{text-decoration:underline}
.btn,button{display:inline-block;border:0;border-radius:9px;padding:11px 16px;background:#2457c5;color:#fff;font-weight:650;cursor:pointer}
.btn.secondary,button.secondary{background:#e9eef8;color:#1d3157}
.btn.danger,button.danger{background:#9b2c2c}
input,textarea{width:100%;padding:12px;border:1px solid #ccd5e3;border-radius:9px;font:inherit;margin:6px 0 16px}
textarea{min-height:330px;resize:vertical;font-family:ui-monospace,Consolas,monospace;font-size:13px}
label{font-weight:650;font-size:14px}article{padding:16px 0;border-bottom:1px solid #e7ebf2}
article:last-child{border-bottom:0}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.space{justify-content:space-between}.status{font-size:12px;border-radius:30px;padding:5px 9px;background:#edf2fa;color:#35496b}
.notice{padding:12px 14px;border-radius:10px;background:#eef7ee;color:#225c2b;margin-bottom:16px}
.warning{padding:12px 14px;border-radius:10px;background:#fff7e6;color:#7b4b00;margin-bottom:16px}
.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.inline{display:inline}
footer{max-width:1080px;margin:20px auto 50px;padding:0 20px;color:#718096;font-size:12px}
@media(max-width:650px){main{margin:20px auto}.panel{padding:18px}h1{font-size:22px}}
"""

def esc(value) -> str:
    text = "" if value is None else str(value)
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;")
                .replace("'", "&#x27;"))

def page(title: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · {APP_NAME}</title><style>{CSS}</style></head>
<body><header><strong>{APP_NAME}</strong><small>Private dashboard for Digital Content Gate</small></header>
<main>{body}</main><footer>Only the authorised Google account can access this dashboard. OAuth tokens are kept in server memory and are not displayed.</footer></body></html>"""
    return HTMLResponse(html)

def callback_url(request: Request) -> str:
    base = APP_BASE_URL or str(request.base_url).rstrip("/")
    return base + "/oauth/callback"

def current_session(request: Request):
    sid = request.session.get("sid")
    if not sid:
        return None
    return USER_SESSIONS.get(sid)

def login_required(request: Request):
    session = current_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    return session

def check_csrf(request: Request, session: dict, form_value: str):
    expected = session.get("csrf", "")
    if not expected or not secrets.compare_digest(expected, form_value or ""):
        raise HTTPException(status_code=403, detail="Invalid form token. Refresh the page and try again.")

async def get_access_token(session: dict) -> str:
    tokens = session.get("tokens", {})
    expires_at = float(tokens.get("expires_at", 0))
    access_token = tokens.get("access_token", "")
    if access_token and expires_at > time.time() + 60:
        return access_token

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Google authorisation expired. Sign in again.")

    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if response.is_error:
        raise HTTPException(status_code=401, detail="Could not refresh Google access. Sign in again.")
    new_tokens = response.json()
    tokens["access_token"] = new_tokens["access_token"]
    tokens["expires_at"] = time.time() + int(new_tokens.get("expires_in", 3600))
    tokens["refresh_token"] = new_tokens.get("refresh_token", refresh_token)
    session["tokens"] = tokens
    return tokens["access_token"]

async def blogger_request(session: dict, method: str, path: str, *, params=None, body=None):
    token = await get_access_token(session)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method, f"{BLOGGER_API}{path}", headers=headers, params=params, json=body
        )
    if response.is_error:
        try:
            detail = response.json().get("error", {}).get("message", "Blogger API request failed.")
        except Exception:
            detail = "Blogger API request failed."
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json() if response.content else {}

async def get_blog(session: dict) -> dict:
    if session.get("blog"):
        return session["blog"]
    blog = await blogger_request(
        session, "GET", "/blogs/byurl", params={"url": BLOG_URL}
    )
    if not blog.get("id"):
        raise HTTPException(status_code=404, detail="The configured Blogger blog was not found.")
    session["blog"] = blog
    return blog

async def list_posts(session: dict, blog_id: str):
    items = []
    for status in ("live", "draft"):
        result = await blogger_request(
            session, "GET", f"/blogs/{blog_id}/posts",
            params={"status": status, "maxResults": 50, "fetchBodies": "true"},
        )
        for post in result.get("items", []):
            post["_dashboard_status"] = status
            items.append(post)
    items.sort(key=lambda p: p.get("updated", ""), reverse=True)
    return items

def csrf_input(session: dict) -> str:
    return f'<input type="hidden" name="csrf" value="{esc(session.get("csrf", ""))}">'

def error_page(message: str, status_code: int = 400):
    body = f'<section class="panel"><h1>تعذر إكمال العملية</h1><div class="warning">{esc(message)}</div><a class="btn secondary" href="/dashboard">العودة للوحة</a></section>'
    return HTMLResponse(page("Error", body).body, status_code=status_code)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if current_session(request):
        return RedirectResponse("/dashboard", status_code=303)
    body = f"""
<section class="panel">
<h1>إدارة مدونة بوابة المحتوى الرقمي</h1>
<p>سجّل الدخول بحساب Google الذي يملك المدونة. سيطلب التطبيق إذن Blogger حتى يعرض المقالات ويسمح بتعديلها.</p>
<div class="warning">هذه لوحة خاصة. لن يتم نشر مقال جديد تلقائيًا؛ إنشاء المقالات يبدأ كمسودة، والنشر يحتاج إجراءً منفصلًا منك.</div>
<a class="btn" href="/login">الدخول باستخدام Google</a>
<p class="muted" style="margin-top:18px">الحساب المسموح: {esc(ADMIN_EMAIL)}</p>
</section>"""
    return page("Sign in", body)

@app.get("/login")
async def login(request: Request):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return error_page("لم تكتمل إعدادات Google OAuth بعد. أضف GOOGLE_CLIENT_ID و GOOGLE_CLIENT_SECRET في إعدادات الخدمة.", 503)
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": callback_url(request),
        "response_type": "code",
        "scope": "openid email https://www.googleapis.com/auth/blogger",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=302)

@app.get("/oauth/callback", name="oauth_callback")
async def oauth_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        return error_page("لم يكتمل تفويض Google: " + error, 400)
    expected = request.session.get("oauth_state", "")
    request.session.pop("oauth_state", None)
    if not code or not state or not expected or not secrets.compare_digest(state, expected):
        return error_page("تعذر التحقق من طلب تسجيل الدخول. ابدأ من جديد.", 400)
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return error_page("إعدادات OAuth غير مكتملة.", 503)

    redirect_uri = callback_url(request)
    async with httpx.AsyncClient(timeout=25) as client:
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        if token_response.is_error:
            return error_page("فشل تبادل رمز Google. راجع عنوان Redirect URI وإعدادات OAuth.", 400)
        tokens = token_response.json()
        user_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens.get('access_token', '')}"},
        )
    if user_response.is_error:
        return error_page("تعذر التحقق من حساب Google.", 403)
    user = user_response.json()
    email = str(user.get("email", "")).lower()
    if email != ADMIN_EMAIL or not user.get("email_verified", False):
        return error_page("هذا الحساب غير مخوّل لإدارة المدونة.", 403)

    sid = secrets.token_urlsafe(32)
    USER_SESSIONS[sid] = {
        "email": email,
        "csrf": secrets.token_urlsafe(32),
        "tokens": {
            "access_token": tokens.get("access_token", ""),
            "refresh_token": tokens.get("refresh_token", ""),
            "expires_at": time.time() + int(tokens.get("expires_in", 3600)),
        },
    }
    request.session.clear()
    request.session["sid"] = sid
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, notice: str = ""):
    session = current_session(request)
    if not session:
        return RedirectResponse("/", status_code=303)
    try:
        blog = await get_blog(session)
        posts = await list_posts(session, str(blog["id"]))
    except HTTPException as exc:
        if exc.status_code == 401:
            return RedirectResponse("/", status_code=303)
        return error_page(str(exc.detail), exc.status_code)

    notice_html = ""
    if notice == "saved":
        notice_html = '<div class="notice">تم حفظ التغييرات بنجاح.</div>'
    elif notice == "created":
        notice_html = '<div class="notice">تم إنشاء المقال كمسودة. لم يتم نشره.</div>'
    elif notice == "published":
        notice_html = '<div class="notice">تم نشر المقال.</div>'

    rows = []
    for post in posts:
        post_id = str(post.get("id", ""))
        status = post.get("_dashboard_status", "live")
        title = esc(post.get("title") or "(بدون عنوان)")
        updated = esc(post.get("updated", "")[:10])
        badge = "مسودة" if status == "draft" else "منشور"
        action = f'<a class="btn secondary" href="/posts/{esc(post_id)}">فتح وتعديل</a>'
        if status == "draft":
            action += f"""
<form class="inline" method="post" action="/posts/{esc(post_id)}/publish">
{csrf_input(session)}<label class="muted">اكتب PUBLISH للتأكيد</label>
<input style="width:145px;margin:0 5px" name="confirmation" required pattern="PUBLISH" placeholder="PUBLISH">
<button class="danger" type="submit">نشر المسودة</button></form>"""
        link = post.get("url")
        link_html = f'<a href="{esc(link)}" target="_blank" rel="noopener">عرض المقال</a>' if link else ""
        rows.append(f'<article><div class="row space"><strong>{title}</strong><span class="status">{badge}</span></div><p class="muted">آخر تحديث: {updated}</p><div class="actions">{action}{link_html}</div></article>')

    body = f"""
<section class="panel">
<div class="row space"><div><h1>لوحة المقالات</h1><p>المدونة: <a href="{esc(BLOG_URL)}" target="_blank" rel="noopener">{esc(BLOG_URL)}</a></p><p class="muted">تم تسجيل الدخول باسم {esc(session.get("email"))}</p></div>
<form method="post" action="/logout">{csrf_input(session)}<button class="secondary" type="submit">تسجيل الخروج</button></form></div>
{notice_html}
<div class="actions"><a class="btn" href="/posts/new">إنشاء مقال جديد كمسودة</a><a class="btn secondary" href="/dashboard">تحديث القائمة</a></div>
</section>
<section class="panel"><h2>المقالات ({len(posts)})</h2>{''.join(rows) if rows else '<p>لم يتم العثور على مقالات.</p>'}</section>
"""
    return page("Dashboard", body)

@app.get("/posts/new", response_class=HTMLResponse)
async def new_post(request: Request):
    session = current_session(request)
    if not session:
        return RedirectResponse("/", status_code=303)
    body = f"""
<section class="panel"><h1>مقال جديد</h1>
<p>سيُحفظ المقال كمسودة في Blogger ولن يُنشر في هذه الخطوة.</p>
<form method="post" action="/posts">
{csrf_input(session)}
<label>عنوان المقال</label><input name="title" required maxlength="300">
<label>التصنيفات (افصل بينها بفاصلة)</label><input name="labels">
<label>محتوى المقال بصيغة HTML</label><textarea name="content" required placeholder="<h2>عنوان فرعي</h2>\n<p>محتوى المقال...</p>"></textarea>
<div class="actions"><button type="submit">حفظ كمسودة</button><a class="btn secondary" href="/dashboard">إلغاء</a></div></form></section>"""
    return page("New draft", body)

@app.post("/posts")
async def create_post(request: Request):
    session = current_session(request)
    if not session:
        return RedirectResponse("/", status_code=303)
    form = await request.form()
    check_csrf(request, session, str(form.get("csrf", "")))
    title = str(form.get("title", "")).strip()
    content = str(form.get("content", "")).strip()
    labels = [x.strip() for x in str(form.get("labels", "")).split(",") if x.strip()]
    if not title or not content:
        return error_page("العنوان والمحتوى مطلوبان.", 400)
    blog = await get_blog(session)
    await blogger_request(session, "POST", f"/blogs/{blog['id']}/posts",
        params={"isDraft": "true"},
        body={"kind": "blogger#post", "blog": {"id": blog["id"]},
              "title": title, "content": content, "labels": labels})
    return RedirectResponse("/dashboard?notice=created", status_code=303)

@app.get("/posts/{post_id}", response_class=HTMLResponse)
async def edit_post(request: Request, post_id: str):
    session = current_session(request)
    if not session:
        return RedirectResponse("/", status_code=303)
    blog = await get_blog(session)
    post = await blogger_request(session, "GET", f"/blogs/{blog['id']}/posts/{post_id}")
    labels = ", ".join(post.get("labels", []))
    status = "مسودة" if post.get("status") == "DRAFT" else "منشور"
    content = esc(post.get("content", ""))
    body = f"""
<section class="panel"><div class="row space"><div><h1>تعديل المقال</h1><p class="muted">الحالة الحالية: {status}</p></div><a class="btn secondary" href="/dashboard">العودة</a></div>
<form method="post" action="/posts/{esc(post_id)}">
{csrf_input(session)}
<label>عنوان المقال</label><input name="title" required maxlength="300" value="{esc(post.get('title',''))}">
<label>التصنيفات (افصل بينها بفاصلة)</label><input name="labels" value="{esc(labels)}">
<label>محتوى المقال بصيغة HTML</label><textarea name="content" required>{content}</textarea>
<button type="submit">حفظ التعديلات</button></form>
<p class="muted">تعديل مقال منشور يحدّث نسخته الحية. لا تغيّر رابط المقال (Permalink) من هنا.</p>
</section>"""
    return page("Edit post", body)

@app.post("/posts/{post_id}")
async def update_post(request: Request, post_id: str):
    session = current_session(request)
    if not session:
        return RedirectResponse("/", status_code=303)
    form = await request.form()
    check_csrf(request, session, str(form.get("csrf", "")))
    title = str(form.get("title", "")).strip()
    content = str(form.get("content", "")).strip()
    labels = [x.strip() for x in str(form.get("labels", "")).split(",") if x.strip()]
    if not title or not content:
        return error_page("العنوان والمحتوى مطلوبان.", 400)
    blog = await get_blog(session)
    await blogger_request(session, "PUT", f"/blogs/{blog['id']}/posts/{post_id}",
        body={"kind": "blogger#post", "id": post_id, "blog": {"id": blog["id"]},
              "title": title, "content": content, "labels": labels})
    return RedirectResponse("/dashboard?notice=saved", status_code=303)

@app.post("/posts/{post_id}/publish")
async def publish_post(request: Request, post_id: str):
    session = current_session(request)
    if not session:
        return RedirectResponse("/", status_code=303)
    form = await request.form()
    check_csrf(request, session, str(form.get("csrf", "")))
    if str(form.get("confirmation", "")).strip() != "PUBLISH":
        return error_page("لم يتم النشر لأن عبارة التأكيد غير صحيحة.", 400)
    blog = await get_blog(session)
    post = await blogger_request(session, "GET", f"/blogs/{blog['id']}/posts/{post_id}")
    if post.get("status") != "DRAFT":
        return error_page("يمكن استخدام هذا الإجراء للمسودات فقط.", 409)
    await blogger_request(session, "POST", f"/blogs/{blog['id']}/posts/{post_id}/publish")
    return RedirectResponse("/dashboard?notice=published", status_code=303)

@app.post("/logout")
async def logout(request: Request):
    session = current_session(request)
    form = await request.form()
    if session:
        check_csrf(request, session, str(form.get("csrf", "")))
        sid = request.session.get("sid")
        if sid:
            USER_SESSIONS.pop(sid, None)
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "digital-content-gate-manager"}
