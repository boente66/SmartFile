from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OrganizationFeature:
    code: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class OrganizationFeatureSet:
    profile_code: str
    profile_name: str
    features: tuple[OrganizationFeature, ...]

    def has(self, code: str) -> bool:
        return any(feature.code == code for feature in self.features)

    @property
    def codes(self) -> frozenset[str]:
        return frozenset(feature.code for feature in self.features)
