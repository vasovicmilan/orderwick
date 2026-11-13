# Online features (optional)

Everything online is **opt-in**. Running from source, `SERVER_URL` defaults to the local server `http://127.0.0.1:3101`; packaged builds default to `https://orderwick.com`;
with it empty (`ORDERWICK_SERVER=""`) the game has no network code path active and the Online screen only says "not available in this build". It is also never active in DEV mode.

## What the player sees
Menu → **Online**. The first time, the screen asks for the **activation key** from the player's account on the website
(`OW-XXXX-XXXX-XXXX`, typed or pasted with Ctrl+V). The server checks it and counts the install; after that the screen lists exactly what will be sent
(below) and asks for consent. If the key is later revoked or no longer fits the install limit, the next visit to the screen notices, forgets the key and
online features stay off until a valid key is entered (a network problem never locks anybody out). Consent is versioned
(`ONLINE_CONSENT_VERSION`): if the data we send ever changes, the player is asked again. Turning it off, exporting or deleting the account
is possible from the same screen; the game works offline at any time.

## What is sent, and why
| Data | Why | Kept |
|---|---|---|
| Activation key + a random install id (server stores only a hash of the install id) | to check the key and count how many computers use it | until the key is reset or the account deleted |
| Random player id + secret key (server stores only a hash of the key) | to recognise your account without e-mail or password | until you delete the account |
| Nickname you choose | public leaderboard | until you change/delete |
| Game version, OS name | updates and compatibility | with the account |
| Your moves for each round (e.g. `c3>c5`, `u`, `x`) and the elapsed time | the server replays them to prove the result is real | discarded after verification; only totals are stored |
| Nothing extra for achievements and coins | the server counts them itself from the verified moves above; the game only receives and shows the result and lets it overwrite its local trophies (offline play earns no coins) | counters, unlock dates and the coin ledger until you delete the account |
| Nothing extra for owned items | the game downloads the pictures and colour files (PNG/JSON data, never code) of the cards, looks and themes you own or have bought; each file is checked for type, size and SHA-256 before use, kept in your data folder, and the game falls back to its built-in look when offline | the list of items you own until you delete the account |
| Your IP address | rate limiting | memory only; web-server logs for `LOG_RETENTION_DAYS` days |

No analytics, no advertising identifiers, no cookies in the game. Public on the leaderboard: nickname, score, level, moves, time, date, and an "AI" badge for agent accounts.

## Protocol (server is authoritative)
0. `POST /api/v1/activation {code, installId, platform}` (player key attached when there is one, so player and website account get linked) → `{ok, name, activations:{used,max}}`.
   Errors: `bad_key`, `not_found`, `forbidden` (revoked / account suspended), `activation_limit` (409), `rate_limited`. The server can additionally
   require it for ranked desktop runs (`REQUIRE_ACTIVATION=1`, error `activation_required`). The browser demo needs no key.
1. `POST /api/v1/players` → id + key. All other calls use `Authorization: Bearer <id>.<key>`.
2. `POST /runs {mode, level}` → run id + first board (`kinds`, `spec`). Daily: `GET /daily`.
3. The client plays; every accepted move/undo/rescue is appended to the round log.
4. `POST /runs/:id/rounds {events, elapsed}` → server replays the log; accepted → gain, score, next level (the server decides the level).
5. `POST /runs/:id/restart {events}` (new board, costs 50 points; the daily board restarts for free) and `POST /runs/:id/finish`.
If the server cannot be reached or rejects a result, the run silently continues **offline and unranked** and the player is told once.

## AI agents
Agents play with the same client and `ORDERWICK_AGENT_KEY` (never written to disk). Their accounts are created by the server admin and are
labelled "AI" in the leaderboard (filter: all / human / AI). Humans cannot take names such as "Claude".

## Honest limits
A server cannot tell a human from a program that solves boards offline; that is why agents are labelled instead of banned, and why rankings
are per-mode bests with server-side time rules.

## Legal summary (not legal advice)
Controller: Milan Vasovic. Basis: consent for the online features (GDPR art. 6(1)(a)); the offline game processes nothing. Rights: access/export,
rectification (rename) and erasure are built into the game. Have the privacy policy and terms on the server reviewed before launch.

## Server address and path
`SERVER_URL` (or the environment variable `ORDERWICK_SERVER`) is the full base address, including a path prefix if the server lives under one,
for example `https://orderwick.com`. The game appends `/api/v1/...` itself.

## Browser version
The browser game plays the same rules but never receives the hidden cards: `POST /runs {client:"web"}` returns the visible state only
(hidden cards are `null`), every move is sent to `POST /runs/:id/move {event}` and the server answers with what is face up now, and a win is verified from the
moves the server stored. Desktop clients are unchanged.
