# Changelog

All notable changes to `hamqth-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `--transport streamable-http` now says where it bound, and the help text says
  it too. It binds `127.0.0.1`, and FastMCP takes no host option, so it was
  never reachable from another machine or from outside a container — and nothing
  said so. The bind address is unchanged: loopback-only is deliberate for a
  server that holds credentials and has no authentication of its own.

## [0.5.2] — 2026-10-26

### Fixed

- `--version` and `--help` now print and exit. They were ignored, so the
  command started the MCP server on stdio and waited for JSON-RPC — leaving a
  FastMCP banner on screen and an apparently hung terminal. Seven servers in
  this fleet already behaved correctly; this brings the rest in line, and a
  test asserts it.

## [0.5.1] — 2026-10-26

- A release should appear on the Releases page
- Move every Node 20 action to its first Node 24 major
- The locked-dependency audit blocked every release
- Four upgrades arrived as 57 pull requests
- Nothing was auditing the lockfile
- Close every open security advisory in the lockfile
- A release is a workflow, not a merge
- Bump certifi from 2026.7.22 to 2026.10.19
- Make the publish gate's http:// check portable
- Assert that certifi is declared, not merely imported

## [0.5.0] — 2026-10-12

**Upgrading:** a tool that fails now returns `isError: true` instead of a successful result whose
payload contained an `error` key. Anything reading `result["error"]` should read the error flag.
No decision changed — an empty DX spot feed is still a successful answer with `total: 0`.

**Also in this release:** the `prg` parameter sent to HamQTH said `adif-mcp` and now says
`hamqth-mcp`, so HamQTH's operator sees this server's traffic under its own name.


- **`E501` is adopted** (#23, qso-graph-devel#70). It was deliberately ignored while the rules that
  find defects went in first; this is the pass of its own that deferral was waiting for. It reported
  **five lines, none of them a defect**, and all five reflowed with no name shortened — **no
  exemption was needed**, so this repo carries no `noqa` at all.
- One line removed that was not formatting, and is called out rather than slipped in: a
  `monkeypatch.setattr` in `test_mcp_conformance.py` patched `require` on a freshly built
  `PersonaManager` that the next line then discarded, so it had never done anything. It was added
  with #24 two PRs ago. The test it belongs to still passes without it, which is the proof it was
  dead.

- **`certifi` is carried, and all three fetch paths verify against it** (#22, qso-graph-devel#73).
  They used `urllib` with no context, so they trusted whichever root store the running Python was
  built against. On macOS that is `/etc/ssl/cert.pem`, a deliberately *reduced* OpenSSL file — 128
  roots against the system keychain's 158, and current rather than stale. **hamqth.com verifies
  fine against it today**, so this was latent rather than an outage.
- **It matters more here than in the rest of the sweep: the operator's password travels over these
  connections**, in query parameters, because that is how HamQTH's login works. Everywhere else a
  trust problem costs an answer; here the connection carrying a secret is the one being verified.
  Which is also why verification is never disabled — `ssl.CERT_NONE` would make a failing call
  "work" by accepting any certificate from anyone, and on this server that means handing the
  password to whoever presented it.
- Three static checks hold this in `test_security.py` and two runtime ones in `test_tools.py`,
  split that way because the release gate runs the first file with the package **not installed**.
  The "every `urlopen` passes the context" check earns its keep here: there are **three** fetch
  helpers, and adding a context to the one being edited while leaving a sibling behind is exactly
  the mistake it catches.
- **`tests/test_release_gate.py`** asserts that precondition rather than leaving it to be
  remembered: the gate suite may import nothing but the standard library and pytest. solar-mcp's
  0.3.0 publish failed on exactly that, from the same change.

- **Tool execution errors are flagged `isError`** (#24). Every tool returned `{"error": "..."}` on
  failure, which reaches a client as a *successful* call whose payload happens to contain the word
  "error". They now raise `ToolError`, which `fastmcp` reports as `isError: true` with the message
  intact. **No decision changed — only how it is reported.** An unknown callsign is a failed
  lookup; an empty DX spot feed is still a successful answer with `total: 0`.
- **The credential cannot reach the client through an error, and that is now asserted.** This is
  the first server in the sweep holding the operator's HamQTH username and password, and HamQTH's
  login puts the password in query parameters. The client has always caught every fetch exception
  and raised a fixed message so a credential-bearing URL could not leak — but until now that
  message sat in a payload; it is now the failure text a client reads. Two tests drive a sentinel
  secret through a network failure and through HamQTH's own login rejection and assert it never
  appears. HamQTH's "Wrong user name or password" *is* passed on, because that is what a model
  should see; the password that was wrong is not.
- **Every tool declares all four annotation hints** (#24). All eight are read-only,
  non-destructive and idempotent; `openWorldHint` is true for the seven that reach hamqth.com —
  three with the operator's credentials, four on public endpoints — and false for
  `get_version_info`. A test asserts the hints say nothing about which tools use a credential:
  the specification fixes what the four hints mean, and requires clients to treat them as
  untrusted, so a security-relevant claim does not belong there.
- **Fixed: this server told HamQTH it was `adif-mcp`.** The `prg` parameter was hard-coded to
  `"adif-mcp"` in both the login and the query path, so HamQTH's operator saw our traffic
  attributed to a different project. It now sends `hamqth-mcp`.
- **`tests/test_mcp_conformance.py`** asserts all of the above.
- Measured while doing it: issue #24 states 16 error dicts in `src/`; there were **9** — 7 in
  `server.py` and 2 in `client.py`. Fifth repo in the sweep where the stated count ran to
  roughly double the real one, so it is an upper bound rather than a target.

## [0.4.6] — 2026-10-11

- **ruff and mypy run in CI** (qso-graph-devel#66), as a job the `ci-all-green` gate requires.
  Settings follow `adif-mcp`, the reference for every qso-graph Python repo, rather than a style of
  this repo's own. They run once rather than per Python version: both read the source, and neither
  answer changes with the interpreter.
- The two mock JSON stand-ins and every cache read are annotated with the type their caller
  expects, and `_get_text` is typed: it promised a `str` while handing back whatever `urlopen` gave
  it.
- `E501` is deferred rather than adopted (qso-graph-devel#70): what it reports in these repos are
  widths, not defects, and some lines are long because they name a publisher's field exactly.
- `mcp.run` is given the literal fastmcp asks for rather than a `str` that happens to hold the
  right word.
- **`fastmcp` is bounded: `>=4.0,<5`** (qso-graph-devel#60). It was `>=3.0` with no upper bound, and
  these servers are run with `uvx`, which resolves fresh — so a `fastmcp` 5.0 would have reached
  every user automatically, before anything here had been run against it. The floor rises to 4.0
  because that is what is actually tested: every lock in the fleet held a 4.x, and nothing in CI
  has ever exercised 3.x. A claim of 3.x support that no test backs is not support.
- `fastmcp` is locked at 4.1.0, the current release, so CI runs against what a new install gets.
- **The published contact is `maintainers@qso-graph.io`** (qso-graph-devel#69). The `authors` field
  carried a personal address, and that field is what PyPI shows on the package page. Everything in
  qso-graph is open source and open to contribution, so the contact is the project's.

## [0.4.5] — 2026-10-07

- LICENSE: the full GPL-3.0 text. The file held only its opening and a link, so GitHub detected no licence.

## [0.4.4] — 2026-10-06

- PyPI: the Documentation link goes to this package's own page, https://qso-graph.io/servers/hamqth/ (qso-graph/.github#15).
- CI: the release flow (qso-graph/.github TEMPLATES.md). Work lands on `develop`; a release is a
  PR from `develop` into `main`, and merging it publishes to PyPI and the MCP Registry, verifies both
  and tags the release. CI runs on `develop` too, and PRs into `main` must come from `develop` or a
  `security/` branch.

## [0.4.3] — 2026-10-04

Documentation only; no code changes. Released so the PyPI page shows the corrected README.

### Changed
- README: the credential steps sent users to `pip install adif-mcp` and `adif-mcp persona …`, which no longer handle credentials. Now qso-auth: `persona add`, `provider enable`, `creds set` (#7).
- README: Known Quirks for the 55-minute session refresh (#7).
- README: uvx only, no pip (#6).

## [0.4.2] — 2026-09-28

### Added (CI hygiene)

- **MCP Registry sync** — `publish.yml` publishes to the [Official MCP Registry](https://registry.modelcontextprotocol.io)
  after each PyPI publish, using GitHub OIDC for auth. Triggered on
  `v*` tag push; no manual steps. The Registry job waits until PyPI
  serves the version, and retries. Pattern documented in
  [qso-graph/.github/TEMPLATES.md](https://github.com/qso-graph/.github/blob/main/TEMPLATES.md).
- **Registry version badge** in README — PyPI and Registry versions
  are visible side-by-side so any drift between publishing surfaces
  is immediately apparent.
- **Release gates** — the tag must match `pyproject.toml`, and a
  `verify` job fails the release unless PyPI and the MCP Registry
  both serve the new version.

### Fixed

- The Official MCP Registry listed hamqth-mcp at 0.2.0. This release brings it current.

## [0.4.1] — 2026-05-16

### Added
- New tool `get_version_info` — returns `{service_name, service_version, spec_version}`
  for fleet identity attestation. Tracks [IONIS-AI/ionis-devel#49](https://github.com/IONIS-AI/ionis-devel/issues/49).
- `__spec_version__` pinned to `hamqth-com-v1`.
- L2 unit tests HAMQTH-L2-046 through HAMQTH-L2-050.
- `.github/workflows/ci.yml` — PR-gating CI (py3.10-3.13 matrix).

### Changed
- `__init__.py` modernized to fleet pattern (`Final` types).

## [0.4.0] — Previous release
- See git history for changes prior to the changelog being introduced.
