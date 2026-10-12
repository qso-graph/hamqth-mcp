"""Conformance with the Model Context Protocol, revision 2026-07-28.

Nothing in this project's documents required this until 2026-10-11 — not
CLAUDE.md, not .claude/rules/security.md, not MCP-SECURITY-FRAMEWORK.md, not
qso-graph-spec. We documented how to *publish* an MCP server in detail and
never wrote down what makes one *valid*, which is how a missing ``isError`` and
missing annotations reached all 22 servers in the fleet unnoticed.

So these are asserted rather than trusted. ``get_version_info`` is the
cautionary case: a fleet convention nobody tested, which drifted.

Follows ``adif-mcp``, ``solar-mcp``, ``pota-mcp``, ``wspr-mcp`` and
``iota-mcp``. **What is new here is credentials.** This is the first server in
the sweep that holds the operator's HamQTH username and password, and flagging
an error means the message now reaches the client as the failure text rather
than sitting in a payload. HamQTH's login puts the password in query
parameters, so a message carrying a URL would carry the password with it.
``TestNoFailurePathCarriesTheSecret`` drives every failure mode with a sentinel
secret and asserts it never appears.

Test IDs: HAMQTH-C01 onward.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastmcp.exceptions import ToolError

os.environ["HAMQTH_MCP_MOCK"] = "1"

from hamqth_mcp import server  # noqa: E402

ANNOTATION_HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")

# The three that send the operator's credentials, and the four that use
# HamQTH's public endpoints. Both reach hamqth.com; the split is recorded
# because it is the thing a reader most needs to know about this server.
NEEDS_CREDENTIALS = {"hamqth_lookup", "hamqth_bio", "hamqth_activity"}
PUBLIC_ENDPOINTS = {"hamqth_dxcc", "hamqth_dx_spots", "hamqth_rbn", "hamqth_verify_qso"}
READS_HAMQTH = NEEDS_CREDENTIALS | PUBLIC_ENDPOINTS
ANSWERS_FROM_THE_PACKAGE = {"get_version_info"}


def _tools() -> dict[str, object]:
    return {t.name: t for t in asyncio.run(server.mcp.list_tools())}


def _wire(tool: object) -> dict[str, object]:
    """The serialised annotations, which is what a client reads."""
    annotations = getattr(tool, "annotations", None)
    assert annotations is not None, "tool declares no annotations"
    return annotations.model_dump(by_alias=True, exclude_none=True)


def _call(name: str):
    """The underlying function of a registered tool."""
    tool = getattr(server, name)
    return getattr(tool, "fn", tool)


class TestToolAnnotations:
    def test_every_tool_declares_all_four_hints(self) -> None:
        """HAMQTH-C01: the defaults are pessimistic, so silence is the wrong answer."""
        for name, tool in _tools().items():
            wire = _wire(tool)
            for hint in ANNOTATION_HINTS:
                assert hint in wire, f"{name} omits {hint} on the wire; got {sorted(wire)}"

    def test_every_tool_reads_and_none_writes(self) -> None:
        """HAMQTH-C02: the three hints that describe effect.

        Every tool here looks something up. Nothing writes to HamQTH, and
        nothing writes a credential — the keyring is read, never updated.
        """
        for name, tool in _tools().items():
            wire = _wire(tool)
            assert wire["readOnlyHint"] is True, name
            assert wire["destructiveHint"] is False, name
            assert wire["idempotentHint"] is True, name

    def test_open_world_is_read_per_tool(self) -> None:
        """HAMQTH-C03: seven reach hamqth.com; one does not."""
        tools = _tools()
        assert set(tools) == READS_HAMQTH | ANSWERS_FROM_THE_PACKAGE
        for name in READS_HAMQTH:
            assert _wire(tools[name])["openWorldHint"] is True, name
        for name in ANSWERS_FROM_THE_PACKAGE:
            assert _wire(tools[name])["openWorldHint"] is False, name

    def test_annotations_do_not_advertise_the_credential_split(self) -> None:
        """HAMQTH-C04: three of these use a stored secret, and the hints do not say so.

        That is deliberate, and worth asserting so nobody later "improves" it.
        The four hints have fixed meanings in the specification; none of them
        means "this reads your keyring", and a client is required to treat
        annotations as untrusted anyway. Inventing a meaning for them would put
        a security-relevant claim in the one place the specification says must
        not be trusted.
        """
        tools = _tools()
        for name in NEEDS_CREDENTIALS:
            assert set(_wire(tools[name])) <= set(ANNOTATION_HINTS) | {"title"}, (
                f"{name} declares an annotation outside the specification's set"
            )


class TestToolErrorsAreFlagged:
    """A tool execution error belongs in the result with ``isError: true``.

    The specification states the cost of getting this wrong: otherwise "the LLM
    would not be able to see that an error occurred and self-correct". These
    returned ``{"error": "..."}`` as a *successful* result until #24.
    """

    @pytest.fixture
    def broken(self, monkeypatch):
        """A client whose every call fails the way an unreachable service does."""
        class Broken:
            def __getattr__(self, _name):
                def fail(*_args, **_kwargs):
                    raise RuntimeError("HamQTH request failed — check network connectivity")
                return fail

        monkeypatch.setattr(server, "_client", lambda persona: Broken())
        monkeypatch.setattr(server, "_public", lambda: Broken())

    UPSTREAM_CASES = [
        ("hamqth_lookup", {"persona": "p", "callsign": "KI7MT"}),
        ("hamqth_bio", {"persona": "p", "callsign": "KI7MT"}),
        ("hamqth_activity", {"persona": "p", "callsign": "KI7MT"}),
        ("hamqth_dxcc", {"query": "KI7MT"}),
        ("hamqth_dx_spots", {}),
        ("hamqth_rbn", {}),
        ("hamqth_verify_qso", {"mycall": "KI7MT", "hiscall": "K1JT",
                               "date": "20260101", "band": "20m"}),
    ]

    def test_the_cases_cover_every_tool_that_reaches_hamqth(self) -> None:
        """HAMQTH-C09: the parametrisation below cannot silently miss one."""
        assert {name for name, _ in self.UPSTREAM_CASES} == READS_HAMQTH

    @pytest.mark.parametrize("name,kwargs", UPSTREAM_CASES)
    def test_an_upstream_failure_is_flagged(self, broken, name, kwargs) -> None:
        """HAMQTH-C10: every tool that can fail, not a sample of them."""
        with pytest.raises(ToolError, match="HamQTH request failed"):
            _call(name)(**kwargs)

    def test_an_unknown_callsign_is_flagged(self, monkeypatch) -> None:
        """HAMQTH-C11: a lookup HamQTH has no record for.

        This was ``{"callsign": ..., "error": "Not found"}`` — a successful
        result whose payload said it had failed, which a caller could not tell
        apart from the callsign's details.
        """
        from hamqth_mcp.client import HamQTHClient

        # Mock mode answers lookup from carried XML and never calls
        # _xml_request, so the patch below would not be reached with it on.
        monkeypatch.delenv("HAMQTH_MCP_MOCK", raising=False)
        client = HamQTHClient()
        monkeypatch.setattr(client, "_xml_request", lambda *a, **k: _empty_xml())
        monkeypatch.setattr(server, "_client", lambda persona: client)
        with pytest.raises(ToolError, match="no record for ZZ9ZZZ"):
            _call("hamqth_lookup")(persona="p", callsign="ZZ9ZZZ")

    def test_a_missing_credential_is_flagged_and_says_what_to_do(self, monkeypatch) -> None:
        """HAMQTH-C12: the most useful error this server has.

        A persona with no stored HamQTH credential is the common first-run
        failure. ``PersonaManager`` already answers it with the command that
        fixes it; flagging it means the model sees a failure and can pass that
        instruction on rather than reporting a successful empty lookup.
        """
        from qso_graph_auth.identity import SecretMissing

        def no_creds(persona, provider, prefer=None):
            raise SecretMissing(persona, provider,
                                f"Missing credentials for {provider} on persona '{persona}' "
                                f"(run: qso-auth creds set {persona} {provider})")

        monkeypatch.delenv("HAMQTH_MCP_MOCK", raising=False)
        monkeypatch.setattr(server, "_clients", {})
        monkeypatch.setattr(server._pm(), "require", no_creds, raising=False)
        monkeypatch.setattr(server, "_pm", lambda: type("PM", (), {"require": staticmethod(no_creds)})())
        with pytest.raises(ToolError, match="qso-auth creds set"):
            _call("hamqth_lookup")(persona="nosuch", callsign="KI7MT")


def _empty_xml():
    """An XML root with no <search> element — HamQTH's "no record" answer."""
    import xml.etree.ElementTree as ET

    return ET.fromstring('<HamQTH xmlns="https://www.hamqth.com"></HamQTH>')


class TestNoFailurePathCarriesTheSecret:
    """The reason this repo needed more care than the five before it.

    HamQTH's login puts the password in query parameters, which the client has
    always known: ``_get_xml`` catches every exception and raises a fixed
    message precisely so a credential-bearing URL cannot reach an error. Since
    #24 that message is no longer buried in a payload — it is the failure text
    the client sees. So the property is asserted rather than left to the
    comment that asserts it in prose.
    """

    SENTINEL = "s3nt1nel-not-a-real-password"

    def _client_with_secret(self):
        from hamqth_mcp.client import HamQTHClient

        client = HamQTHClient()
        client.configure("KI7MT", self.SENTINEL)
        return client

    def test_a_network_failure_message_does_not_carry_it(self, monkeypatch) -> None:
        """HAMQTH-C20: the login URL holds the password; the error must not."""
        import urllib.request

        client = self._client_with_secret()

        def explode(*_args, **_kwargs):
            # urllib's own errors quote the URL, which is the whole hazard.
            raise OSError(f"failed opening https://www.hamqth.com/xml.php?u=KI7MT&p={self.SENTINEL}")

        monkeypatch.setattr(urllib.request, "urlopen", explode)
        monkeypatch.delenv("HAMQTH_MCP_MOCK", raising=False)
        monkeypatch.setattr(server, "_client", lambda persona: client)
        with pytest.raises(ToolError) as caught:
            _call("hamqth_lookup")(persona="p", callsign="KI7MT")
        assert self.SENTINEL not in str(caught.value), "the password reached the client"

    def test_a_login_rejection_message_does_not_carry_it(self, monkeypatch) -> None:
        """HAMQTH-C21: HamQTH's own refusal is passed on; the secret is not.

        "Wrong user name or password" is exactly what a model should see. The
        password that was wrong is exactly what it should not.
        """
        import xml.etree.ElementTree as ET

        client = self._client_with_secret()
        monkeypatch.setattr(
            client, "_get_xml",
            lambda url: ET.fromstring(
                '<HamQTH xmlns="https://www.hamqth.com">'
                "<session><error>Wrong user name or password</error></session></HamQTH>"
            ),
        )
        monkeypatch.delenv("HAMQTH_MCP_MOCK", raising=False)
        monkeypatch.setattr(server, "_client", lambda persona: client)
        with pytest.raises(ToolError) as caught:
            _call("hamqth_lookup")(persona="p", callsign="KI7MT")
        message = str(caught.value)
        assert "Wrong user name or password" in message
        assert self.SENTINEL not in message, "the password reached the client"


class TestAnEmptyAnswerIsNotAnError:
    """The distinction the specification draws."""

    def test_a_spot_feed_with_nothing_on_it_is_a_successful_call(self, monkeypatch) -> None:
        """HAMQTH-C30: a quiet cluster is an answer, not a failure."""
        class Quiet:
            def dx_spots(self, **_kwargs):
                return []

        monkeypatch.setattr(server, "_public", lambda: Quiet())
        answer = _call("hamqth_dx_spots")()
        assert isinstance(answer, dict)
        assert answer["total"] == 0

    def test_a_normal_lookup_is_a_successful_call(self) -> None:
        """HAMQTH-C31: the control, from mock mode."""
        answer = _call("hamqth_lookup")(persona="p", callsign="KI7MT")
        assert answer["callsign"]


class TestVersionInfoShape:
    def test_it_matches_the_shape_the_fleet_returns(self) -> None:
        """HAMQTH-C40: the convention that drifted because nobody asserted it."""
        info = _call("get_version_info")()
        assert info["service_name"] == "hamqth-mcp"
        assert info["service_version"]
        assert info["spec_version"]


class TestRegistration:
    def test_the_eight_tools_a_client_sees(self) -> None:
        """HAMQTH-C50: calling a function directly is not proof a client can."""
        assert set(_tools()) == READS_HAMQTH | ANSWERS_FROM_THE_PACKAGE
