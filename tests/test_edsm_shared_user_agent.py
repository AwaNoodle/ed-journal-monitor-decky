"""Both EDSM clients must share the same User-Agent string via constants.py."""


def test_read_client_and_write_client_share_user_agent():
    import inspect

    from src.modules.constants import EDSM_USER_AGENT
    from src.modules.edsm_read_client import EdsmReadClient
    from src.modules.forwarders.edsm_client import EdsmClient
    from src.modules.ssl_context import build_ssl_context

    # EdsmReadClient defaults
    read_client = EdsmReadClient(ssl_context=build_ssl_context())
    assert read_client._user_agent == EDSM_USER_AGENT

    # EdsmClient defaults (uses EDSM_USER_AGENT in its signature)
    sig = inspect.signature(EdsmClient.__init__)
    default_ua = sig.parameters["user_agent"].default
    assert default_ua == EDSM_USER_AGENT
