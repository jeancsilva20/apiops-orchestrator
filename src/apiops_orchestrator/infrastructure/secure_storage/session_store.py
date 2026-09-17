import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from apiops_orchestrator.domain.models.login_session_model import LoginSession

logger = logging.getLogger(__name__)

SESSION_FILE_NAME = ".sen_session"


class SessionStorageError(Exception):
    """Raised when the local session file cannot be persisted. Never carries session content."""


class SessionStore:
    """Stores the login session in a hidden, atomically-written file in the OS temp dir.

    The same store exposes the reader used by subsequent application executions.
    """

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.directory = Path(directory) if directory else Path(tempfile.gettempdir())
        self.session_path = self.directory / SESSION_FILE_NAME

    def save(self, session: LoginSession) -> None:
        # The privileged super-admin token lives in memory only: dropping the
        # field here guarantees it never touches the disk for ANY profile.
        payload = session.model_dump_json(exclude={"adminAccessToken"})
        temp_path: Optional[Path] = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=f"{SESSION_FILE_NAME}.", suffix=".tmp", dir=str(self.directory)
            )
            temp_path = Path(temp_name)
            with os.fdopen(fd, "w", encoding="utf-8") as file_handle:
                file_handle.write(payload)
                file_handle.flush()
                os.fsync(file_handle.fileno())
            os.chmod(temp_path, 0o600)
            self._mark_hidden_on_windows(temp_path)
            os.replace(temp_path, self.session_path)
            temp_path = None
        except (OSError, UnicodeError) as exc:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("auth.storage.temp_cleanup_failed")
            raise SessionStorageError(
                "Não foi possível gravar a sessão local (verifique permissões e diretório temporário)."
            ) from exc

    def load(self, now: Optional[datetime] = None) -> Optional[LoginSession]:
        """Load the persisted session; the model is the validation authority.

        Corrupt, legacy (flat) or unknown-profile files fail model validation
        and are treated as "session absent" (forces re-login). A super-admin
        session without the admin token (always absent on disk) loads fine.
        """
        if not self.session_path.is_file():
            return None
        try:
            raw = self.session_path.read_text(encoding="utf-8")
            session = LoginSession.model_validate_json(raw)
        except (OSError, UnicodeError, ValidationError):
            logger.info("auth.session.file_unreadable")
            return None
        current = now or datetime.now(timezone.utc)
        if session.is_expired(current):
            logger.info("auth.session.expired")
            return None
        return session

    @staticmethod
    def _mark_hidden_on_windows(path: Path) -> None:
        if os.name != "nt":
            return
        try:
            import ctypes

            FILE_ATTRIBUTE_HIDDEN = 0x02
            ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_HIDDEN)
        except Exception:
            logger.debug("auth.storage.hidden_attribute_best_effort_failed")
