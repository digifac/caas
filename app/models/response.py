"""Modèles Pydantic pour les réponses JSON/JSONL de l'API de conversion.

Ce module définit les structures de données standardisées pour tous les convertisseurs,
assurant une cohérence entre PDF, DOCX, XLSX et autres formats.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PageJson(BaseModel):
    """Représente une page ou unité logique du document.

    Utilisé par PDF, DOCX, ODT, PPTX, HTML (contenu textuel).
    Pour les formats structurés (XLSX/ODS), voir SheetJson et CellJson.
    """

    model_config = ConfigDict(populate_by_name=True)

    page_idx: int | None = Field(None, description="Index de la page/section")
    markdown_text: str = Field(..., description="Contenu brut (Markdown ou texte)")
    links: list[str] = Field(default_factory=list, description="Liens extraits")


class ConversionResponse(BaseModel):
    """Réponse JSON structurée pour l'API de conversion.

    Format standardisé retourné quand `format=json` est spécifié dans la requête.
    Compatible avec tous les convertisseurs (PDF, DOCX, XLSX, ODT, PPTX, HTML, ODP).
    """

    model_config = ConfigDict(populate_by_name=True)

    format: str = Field(..., description="Format source du document (pdf, docx, xlsx, etc.)")
    pages: list[PageJson] = Field(default_factory=list, description="Liste des pages/sections avec contenu")
    content: str | None = Field(None, description="Contenu Markdown brut (alternative aux pages pour formats simples)")
    metadata: dict = Field(default_factory=dict, description="Métadonnées spécifiques au format")
    request_id: str | None = Field(None, description="ID unique de la requête pour le tracing")
    success: bool = Field(True, description="Statut de réussite")
    timestamp: datetime = Field(default=datetime.utcnow(), description="Horodatage UTC")


class SheetJson(BaseModel):
    """Représente une feuille de calcul (XLSX/ODS).

    Utilisé pour les formats tabulaires avec données structurées.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Nom de la feuille")
    data: list[list[Any]] = Field(default_factory=list, description="Données brutes (liste de listes)")
    headers: list[str] | None = Field(None, description="En-têtes de colonnes si disponibles")


class CellJson(BaseModel):
    """Représente une cellule individuelle (XLSX/ODS).

    Utilisé pour les formats tabulaires avec granularité cellulaire.
    """

    model_config = ConfigDict(populate_by_name=True)

    row: int = Field(..., description="Numéro de ligne")
    col: int = Field(..., description="Numéro de colonne")
    value: Any = Field(None, description="Valeur de la cellule (str, float, None)")


class SlideJson(BaseModel):
    """Représente une diapositive (PPTX/ODP).

    Utilisé pour les présentations avec contenu textuel et tableaux.
    """

    model_config = ConfigDict(populate_by_name=True)

    index: int = Field(..., description="Index de la diapositive")
    title: str | None = Field(None, description="Titre de la diapositive")
    content: list[str] = Field(default_factory=list, description="Liste des paragraphes/texte")
    tables: list[list[list[Any]]] = Field(default_factory=list, description="Tableaux extraits")


class HtmlElementJson(BaseModel):
    """Représente un élément HTML extrait.

    Utilisé pour le convertisseur HTML avec structure d'éléments.
    """

    model_config = ConfigDict(populate_by_name=True)

    tag: str = Field(..., description="Nom de la balise (div, p, h1, etc.)")
    content: str = Field(..., description="Contenu textuel de l'élément")
    attributes: dict = Field(default_factory=dict, description="Attributs HTML extraits")
    children: list[dict] = Field(default_factory=list, description="Enfants récursifs (si applicable)")


class OdtElementJson(BaseModel):
    """Représente un élément ODT (paragraphe, titre, liste).

    Utilisé pour le convertisseur ODT avec structure d'éléments.
    """

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(..., description="Type d'élément (paragraph, heading, list)")
    content: str = Field(..., description="Contenu textuel")
    level: int = Field(0, description="Niveau de hiérarchie pour les titres/listes")


class OdpSlideJson(BaseModel):
    """Représente une diapositive ODP (OpenDocument Presentation).

    Utilisé pour le convertisseur ODP avec frames et listes.
    """

    model_config = ConfigDict(populate_by_name=True)

    index: int = Field(..., description="Index de la diapositive")
    title: str | None = Field(None, description="Titre de la diapositive")
    content: list[str] = Field(default_factory=list, description="Contenu textuel des frames")
    lists: list[list[str]] = Field(default_factory=list, description="Listes à puces/numérotées")


# Événements JSONL standardisés (cohérents entre tous les convertisseurs)
class JsonlEvent(BaseModel):
    """Événement JSONL pour le streaming granulaire.

    Utilisé quand `format=jsonl` est spécifié dans la requête.
    Chaque événement correspond à une unité logique ou un chunk de contenu.
    """

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(..., pattern="^(start|chunk|end)$", description="Type d'événement")
    page_idx: int | None = Field(None, description="Index de la page/section/diapositive")
    markdown_text: str = Field("", description="Contenu du chunk ou données brutes")
    links: list[str] = Field(default_factory=list, description="Liens extraits")
    offset: int = Field(0, description="Décalage dans le document (pour chunking)")
    length: int = Field(0, description="Longueur du chunk")
    metadata: dict = Field(default_factory=dict, description="Métadonnées spécifiques")
