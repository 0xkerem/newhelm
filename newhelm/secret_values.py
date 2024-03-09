from abc import ABC, abstractmethod
from typing import Generic, List, Mapping, Optional, Sequence, Type, TypeVar

from pydantic import BaseModel

from newhelm.general import get_concrete_subclasses


class SecretDescription(BaseModel):
    """How to look up a secret and how to get the value if you don't have it."""

    scope: str
    key: str
    instructions: str


RawSecrets = Mapping[str, Mapping[str, str]]
"""Convenience typing for how the secrets are read from a file."""


BaseSecretType = TypeVar("BaseSecretType", bound="BaseSecret")


# TODO: Consider removing inheritance from BaseModel.
class BaseSecret(ABC, BaseModel):
    """Base class for all secrets."""

    @classmethod
    @abstractmethod
    def description(cls) -> SecretDescription:
        pass

    @classmethod
    @abstractmethod
    def make(cls: Type[BaseSecretType], raw_secrets: RawSecrets) -> BaseSecretType:
        """Read the secret value from `raw_secrets to make this class."""
        pass


def get_all_secrets() -> Sequence[SecretDescription]:
    """Return the descriptions of all possible secrets."""
    secrets = get_concrete_subclasses(BaseSecret)  # type: ignore
    return [s.description() for s in secrets]


class SerializedSecret(BaseModel):
    """Hold a pointer to the secret class in a serializable form."""

    module: str
    qual_name: str

    @staticmethod
    def serialize(secret: BaseSecret):
        return SerializedSecret(
            module=secret.__class__.__module__,
            qual_name=secret.__class__.__qualname__,
        )


RequiredSecretType = TypeVar("RequiredSecretType", bound="RequiredSecret")


class RequiredSecret(BaseSecret):
    """Base class for all required secrets."""

    def __init__(self, value: str):
        super().__init__()
        self._value = value

    @property
    def value(self) -> str:
        """Get the value of the secret."""
        return self._value

    @classmethod
    def make(
        cls: Type[RequiredSecretType], raw_secrets: RawSecrets
    ) -> RequiredSecretType:
        """Raise a MissingSecretValues if desired secret not in raw_secrets."""
        secret = cls.description()
        try:
            return cls(raw_secrets[secret.scope][secret.key])
        except KeyError:
            raise MissingSecretValues([secret])


class MissingSecretValues(LookupError):
    """Exception describing one or more missing required secrets."""

    def __init__(self, descriptions: Sequence[SecretDescription]):
        assert descriptions, "Must have at least 1 description to raise an error."
        self.descriptions = descriptions

    @staticmethod
    def combine(errors: Sequence["MissingSecretValues"]) -> "MissingSecretValues":
        """Combine multiple exceptions into one."""
        descriptions: List[SecretDescription] = []
        for error in errors:
            descriptions.extend(error.descriptions)
        return MissingSecretValues(descriptions)

    def __str__(self):
        message = "Missing the following secrets:\n"
        for d in self.descriptions:
            # TODO Make this nicer.
            message += str(d) + "\n"
        return message


OptionalSecretType = TypeVar("OptionalSecretType", bound="OptionalSecret")


class OptionalSecret(BaseSecret):
    """Base class for all optional secrets."""

    def __init__(self, value: Optional[str]):
        super().__init__()
        self._value = value

    @property
    def value(self) -> Optional[str]:
        """Get the secret value, or None if it wasn't provided."""
        return self._value

    @classmethod
    def make(
        cls: Type[OptionalSecretType], raw_secrets: RawSecrets
    ) -> OptionalSecretType:
        secret = cls.description()
        try:
            return cls(raw_secrets[secret.scope][secret.key])
        except KeyError:
            return cls(None)


_T = TypeVar("_T")


# TODO Consider moving these to dependency_injection.py
class Injector(ABC, Generic[_T]):
    """Base class for delayed injection of a value."""

    @abstractmethod
    def inject(self, raw_secrets: RawSecrets) -> _T:
        pass


class InjectSecret(Injector, Generic[BaseSecretType]):
    def __init__(self, secret_class: Type[BaseSecretType]):
        self.secret_class = secret_class

    def inject(self, raw_secrets: RawSecrets) -> BaseSecretType:
        return self.secret_class.make(raw_secrets)
    
    #def __repr__(self) -> str:
    #    return f"Inject({self.secret_class})"
