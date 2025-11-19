from abc import abstractmethod, ABC

class AuthenticationPort(ABC):
    @abstractmethod
    def authenticate(self) -> str:
        """Authenticates in the API manager."""
        pass