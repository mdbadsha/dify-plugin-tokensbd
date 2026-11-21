import logging
from collections.abc import Mapping

from dify_plugin import ModelProvider
from dify_plugin.errors.model import CredentialsValidateFailedError

from models._tokensbd import fetch_models

logger = logging.getLogger(__name__)


class TokensbdModelProvider(ModelProvider):
    def validate_provider_credentials(self, credentials: Mapping) -> None:
        """Checks the key with ``GET /v1/models``: no model runs, so saving the key costs nothing.

        Raises:
            CredentialsValidateFailedError: tokens.bd refused the key or could not be reached.
        """
        # A key with no plan or balance yet lists no models; it is still saved, and a request then
        # says what to do (top up or choose a plan), so the setup can be finished first.
        try:
            fetch_models(dict(credentials), fresh=True)
        except CredentialsValidateFailedError:
            raise
        except Exception as ex:
            logger.exception("tokens.bd credentials check failed")
            msg = f"Could not check the key with tokens.bd: {ex.__class__.__name__}"
            raise CredentialsValidateFailedError(msg) from ex
