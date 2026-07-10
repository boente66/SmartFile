from abc import ABC, abstractmethod
from app.models.convert_job import ConvertJob


class BaseConvertService(ABC):

    @abstractmethod
    def supports(self, key: str) -> bool:
        """Informa se o service suporta a conversão"""
        pass

    @abstractmethod
    def convert(self, job: ConvertJob):
        pass