"""Reaching a repository: where its API is, and whether a token is needed.

Both matter for the same reason. The configurations this reads live on
baltig.infn.it, not gitlab.com, and several repositories are public — so
an API address fixed at gitlab.com reads somebody else's repository, and a
token sent as an empty string turns a readable public repository into a
401.
"""
import pytest
import requests

from app.services.git_import import (
    _checked,
    _get_file_github,
    _get_file_gitlab,
    _list_files_github,
    github_api,
    gitlab_api,
)


class FakeResponse:
    def __init__(self, status_code=200, text="ok", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    """Records where it was asked to go, and with what headers."""

    def __init__(self, headers=None, response=None):
        self.headers = headers or {}
        self.calls = []
        self.response = response or FakeResponse(payload={"tree": []})

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


# --- where the API is ---------------------------------------------------

def test_a_self_hosted_gitlab_is_read_at_its_own_address():
    """These repositories are on baltig.infn.it; gitlab.com holds nothing
    of theirs."""
    assert gitlab_api("https://baltig.infn.it/lnf-da-control/epik8-sparc.git") \
        == "https://baltig.infn.it/api/v4"


def test_gitlab_com_still_works():
    assert gitlab_api("https://gitlab.com/group/project.git") == "https://gitlab.com/api/v4"


def test_github_com_uses_its_api_host_and_an_enterprise_host_its_own():
    assert github_api("https://github.com/infn-epics/ioc-chart") == "https://api.github.com"
    assert github_api("https://git.example.org/team/repo") == "https://git.example.org/api/v3"


def test_the_request_actually_goes_to_that_address():
    session = FakeSession(response=FakeResponse(payload={"tree": []}))
    _list_files_github(session, "lnf-da-control", "epik8-sparc", "main",
                       "https://git.example.org/api/v3")
    assert session.calls[0][0].startswith("https://git.example.org/api/v3/repos/")


# --- with and without a token -------------------------------------------

def test_reading_a_public_repository_sends_no_authorization_header():
    """An empty Bearer token is rejected outright, so a public repository
    read with one fails where it would otherwise have worked."""
    session = FakeSession(response=FakeResponse(text="beamline: sparc"))
    assert _get_file_gitlab(session, "lnf-da-control/epik8-sparc", "deploy/values.yaml",
                            "main", "https://baltig.infn.it/api/v4") == "beamline: sparc"
    assert "PRIVATE-TOKEN" not in session.headers
    assert "Authorization" not in session.headers


def test_a_token_is_sent_when_there_is_one():
    session = FakeSession(headers={"Authorization": "Bearer abc"},
                          response=FakeResponse(text="x"))
    _get_file_github(session, "o", "r", "p", "main")
    assert session.headers["Authorization"] == "Bearer abc"


# --- what a failure says ------------------------------------------------

def test_without_a_token_a_404_suggests_the_repository_may_be_private():
    """404 and 401 look the same from outside, and "404 Client Error" sends
    somebody to check their spelling when they need a token."""
    with pytest.raises(RuntimeError) as caught:
        _checked(FakeResponse(status_code=404), "deploy/values.yaml", authenticated=False)
    assert "private" in str(caught.value)
    assert "token" in str(caught.value)


def test_with_a_token_the_advice_is_about_the_path_and_the_branch():
    with pytest.raises(RuntimeError) as caught:
        _checked(FakeResponse(status_code=404), "deploy/values.yaml", authenticated=True)
    assert "branch" in str(caught.value)
    assert "private" not in str(caught.value)


def test_the_failing_thing_is_named():
    with pytest.raises(RuntimeError) as caught:
        _checked(FakeResponse(status_code=403), "deploy/values.yaml in epik8-sparc@main",
                 authenticated=False)
    assert "deploy/values.yaml in epik8-sparc@main" in str(caught.value)


def test_other_failures_are_not_dressed_up_as_permission_problems():
    with pytest.raises(requests.HTTPError):
        _checked(FakeResponse(status_code=500), "x", authenticated=True)
