# app/models/pdf_model.py

from dataclasses import dataclass, field
from typing import List
from pathlib import Path


@dataclass
class PDFPage:
    """
    Representa uma página do PDF.
    """
    index: int


@dataclass
class PDFModel:
    """
    Representa um documento PDF carregado.
    Mantém estado de páginas e seleção.
    """

    path: Path
    pages: List[PDFPage] = field(default_factory=list)
    selected_pages: List[int] = field(default_factory=list)

    # -------------------------
    # Informações
    # -------------------------
    def page_count(self) -> int:
        return len(self.pages)

    # -------------------------
    # Seleção
    # -------------------------
    def select_page(self, index: int):

        if index not in self.selected_pages:
            self.selected_pages.append(index)

    def unselect_page(self, index: int):

        if index in self.selected_pages:
            self.selected_pages.remove(index)

    def clear_selection(self):

        self.selected_pages.clear()

    # -------------------------
    # Remover página
    # -------------------------
    def remove_page(self, index: int):

        self.pages = [p for p in self.pages if p.index != index]

        # reorganiza índices
        for i, page in enumerate(self.pages):
            page.index = i

        # limpa seleção inválida
        self.selected_pages = [
            i for i in self.selected_pages if i < len(self.pages)
        ]

    # -------------------------
    # Reordenar páginas
    # -------------------------
    def reorder_pages(self, new_order: List[int]):

        new_pages = [self.pages[i] for i in new_order]

        for i, page in enumerate(new_pages):
            page.index = i

        self.pages = new_pages