# Digital Content Gate Manager

Private Blogger dashboard for `digitalcontentgatehub.blogspot.com`.

## Features
- Google OAuth sign-in restricted to the configured administrator email.
- Lists live posts and drafts.
- Creates new posts as drafts only.
- Edits existing post title, labels, and HTML content.
- Publishes a draft only after the administrator types `PUBLISH`.

## Required environment variables
- `ADMIN_EMAIL`: the Google account allowed to sign in.
- `BLOG_URL`: `https://digitalcontentgatehub.blogspot.com/`
- `APP_BASE_URL`: public HTTPS service origin, without a trailing slash.
- `GOOGLE_CLIENT_ID`: OAuth client ID (added after deployment).
- `GOOGLE_CLIENT_SECRET`: OAuth client secret (added after deployment).
- `SESSION_SECRET`: long random secret used to sign the session cookie.

## Google OAuth configuration
Use the OAuth web application client and add this exact authorised redirect URI:
`https://YOUR-SERVICE.onrender.com/oauth/callback`

Scopes:
- `openid`
- `email`
- `https://www.googleapis.com/auth/blogger`

Keep the consent screen in Testing and add only the administrator as a test user.

## Security notes
- Never commit OAuth secrets to Git.
- OAuth tokens are kept in process memory and are not written to disk or returned to the browser.
- Free Render services can restart or spin down; after a restart, sign in again.
- This is a private administration tool, not a public multi-user CMS.
