# TODO: Ajouter la conversion en JSON/JSONL

Ce fichier liste les étapes pour ajouter le support de l'export JSON et JSONL aux conversions existantes (actuellement Markdown). Chaque étape est courte, simple et réversible.

---

## 📋 Table des matières

- [1. Analyse du code actuel](#1-analyse-du-code-actuel)
- [2. Conception de l'API](#2-conception-de-lapi)
- [3. Implémentation des convertisseurs JSON/JSONL](#3-implémentation-des-convertisseurs-jsonjsonl)
- [4. Tests unitaires et d'intégration](#4-tests-unitaires-et-dintégration)
- [5. Documentation (README.md)](#5-documentation-readmemd)
- [6. Changelog (CHANGELOG.md)](#6-changelog-changlogmd)
- [7. Tests E2E et validation](#7-tests-e2e-et-validation)

---

## 1. Analyse du code actuel

### 1.1 Comprendre la structure actuelle

**Objectif**: Identifier comment les convertisseurs Markdown sont implémentés pour réutiliser le pattern.

**Actions**:
- [ ] Lire `app/converters/base.py` pour comprendre les utilitaires partagés
- [ ] Examiner un convertisseur existant (ex: `app/converters/pdf.py`)
- [ ] Vérifier la structure des données retournées par chaque convertisseur
- [ ] Identifier le format de sortie actuel (Markdown en chaîne)

**Référence**: 
- `app/converters/base.py` - utilitaires communs
- `app/converters/pdf.py` - exemple PDF → Markdown
- `app/streaming.py` - implémentation du streaming

---

### 1.2 Analyser les données de sortie

**Objectif**: Comprendre la structure des données brutes avant conversion en Markdown.

**Actions**:
- [ ] Pour PDF: identifier la structure `(page_idx, markdown_text, urls)`
- [ ] Pour DOCX/ODT/XLSX/PPTX/HTML: identifier les structures de données retournées
- [ ] Documenter le format JSON attendu pour chaque type de fichier

**Format JSON cible**:
```json
{
  "format": "pdf",
  "pages": [
    {
      "index": 0,
      "content": "...",
      "urls": ["..."]
    }
  ],
  "metadata": {...}
}
```

**Format JSONL cible**:
- Une ligne JSON par page/changement de section
- Format: `{"page": N, "content": "...", "urls": [...]}`

---

## 2. Conception de l'API

### 2.1 Définir les endpoints

**Objectif**: Ajouter des paramètres d'export au endpoint existant `/convert`.

**Actions**:
- [ ] Ajouter `?format=json` ou `?format=markdown|json|jsonl` à `/convert`
- [ ] Ajouter `?format=jsonl` pour le format JSONL
- [ ] Définir la réponse par défaut (Markdown) si aucun format non spécifié

**Changement attendu**:
```python
# Actuel
GET /convert?file=... → Markdown string

# Nouveau
GET /convert?file=&format=markdown → Markdown string (défaut)
GET /convert?file=&format=json → JSON object
GET /convert?file=&format=jsonl → JSONL stream (SSE ou raw text)
```

---

### 2.2 Définir le contrat de réponse JSON

**Objectif**: Spécifier la structure exacte du JSON retourné.

**Actions**:
- [ ] Créer un modèle Pydantic pour la réponse JSON (`app/models/response.py`)
- [ ] Inclure: `format`, `pages` (ou `content`), `metadata`, `request_id`
- [ ] Définir les champs optionnels et leurs types

**Modèle proposé**:
```python
class ConversionResponse(BaseModel):
    format: str = "markdown"
    content: Union[str, list[dict]]  # Markdown string ou liste de pages JSON
    metadata: dict = {}
    request_id: str | None = None
    success: bool = True
```

---

### 2.3 Définir le contrat de réponse JSONL

**Objectif**: Spécifier le format JSONL pour les grands documents avec granularité adaptée au chunking.

**Approche recommandée**: Chunk-based avec configuration flexible

```jsonl
# Événements standardisés (cohérents entre tous les convertisseurs)
{"type": "start", "index": 0, "metadata": {...}}           # Début document/section
{"type": "chunk", "content": "...", "offset": 1024, "length": 512}  # Fragment chunké
{"type": "end"}                                             # Fin document/section
```

**Configuration**:
- Paramètre: `CAAS_JSONL_CHUNK_SIZE` (défaut: 1024 caractères)
- Appliqué à tous les convertisseurs textuels (PDF, DOCX, ODT, PPTX, HTML)
- Pour XLSX/ODS (données structurées): une ligne JSONL par ligne de données

**Granularité par type**:
| Type | Unité logique | Granularité |
|------|---------------|-------------|
| PDF | Page | Chunk textuel (1024 chars) |
| DOCX/ODT | Section (para, heading) | Chunk textuel (1024 chars) |
| PPTX | Diapositive | Chunk textuel (1024 chars) |
| HTML | Élément | Chunk textuel (1024 chars) |
| XLSX/ODS | Ligne de données | Une ligne par ligne (chunk optionnel si > 1024 chars) |

**Avantages**:
- Granularité fine pour le streaming et LLM context windows
- Cohérence entre tous les convertisseurs
- Configuration centralisée via `CAAS_JSONL_CHUNK_SIZE`

---

## 3. Implémentation des convertisseurs JSON/JSONL

### 3.1 Ajouter les méthodes de conversion JSON aux convertisseurs existants

**Objectif**: Modifier chaque convertisseur pour supporter l'export JSON.

**Actions par fichier**:

#### `app/converters/base.py` - Utilitaires communs
- [ ] **Étape 3.1.1**: Importer `json` module (`import json`)
- [ ] **Étape 3.1.2**: Ajouter fonction `_to_json_format(data: dict) -> str`:
  ```python
  def _to_json_format(data: dict) -> str:
      return json.dumps(data, ensure_ascii=False, indent=2)
  ```
- [ ] **Étape 3.1.3**: Ajouter fonction `_to_jsonl_format(pages: list[dict]) -> str`:
  ```python
  def _to_jsonl_format(pages: list[dict]) -> str:
      return "\n".join(json.dumps(page, ensure_ascii=False) for page in pages)
  ```

#### `app/converters/pdf.py` - PDF → JSON/JSONL

**Approche**: Chunk textuel par blocs de `CAAS_JSONL_CHUNK_SIZE` caractères (défaut: 1024)

- [ ] **Étape 3.1.4**: Créer modèles Pydantic dans `app/models/response.py`:
  ```python
  class PageJson(BaseModel):
      index: int
      content: str
      urls: list[str] = []
  
  # Événements JSONL standardisés (cohérents avec tous les convertisseurs)
  class JsonlEvent(BaseModel):
      type: str  # "start", "chunk", "end"
      index: int | None = None
      content: str = ""
      offset: int = 0
      length: int = 0
      metadata: dict = {}
  ```

- [ ] **Étape 3.1.5**: Modifier `_extract_pdf_content()` pour extraire données brutes + Markdown:
  ```python
  def _extract_pdf_data(file_bytes: bytes) -> tuple[list[tuple[int, str, list[str]]], int]:
      # ... extraction existante ...
      return results, total_pages
  ```

- [ ] **Étape 3.1.6**: Ajouter méthode `_to_json()` dans `convert_pdf()`:
  ```python
  def convert_pdf(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "json":
          pages, total_pages = _extract_pdf_data(file_bytes)
          return {
              "format": "pdf",
              "pages": [{"index": p[0], "content": p[1], "urls": p[2]} for p in pages],
              "metadata": {"total_pages": total_pages}
          }
  ```

- [ ] **Étape 3.1.7**: Ajouter méthode `_to_jsonl()` dans `convert_pdf()` avec chunking textuel:
  ```python
  def convert_pdf(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "jsonl":
          pages, total_pages = _extract_pdf_data(file_bytes)
          
          chunks = []
          for page in pages:
              # Début page
              chunks.append(JsonlEvent(
                  type="start", 
                  index=page[0], 
                  metadata={"source": "pdf_page"}
              ))
              
              # Chunker le contenu textuel (Markdown) par blocs de CAAS_JSONL_CHUNK_SIZE
              content = page[1]  # Markdown text
              chunk_size = settings.jsonl_chunk_size or 1024
              
              for i in range(0, len(content), chunk_size):
                  chunk_content = content[i:i+chunk_size]
                  chunks.append(JsonlEvent(
                      type="chunk", 
                      content=chunk_content,
                      offset=i,
                      length=len(chunk_content)
                  ))
              
              # Fin page
              chunks.append(JsonlEvent(type="end"))
          
          return "\n".join(json.dumps(e.model_dump(), ensure_ascii=False) for e in chunks)
  ```

**Note**: Le chunking s'applique au contenu textuel (Markdown), pas aux métadonnées. Chaque chunk respecte la taille configurée pour le streaming LLM-friendly.
              # Page start
              chunks.append({"type": "page_start", "index": page["index"]})
              
              # Chunk the content
              content = page["content"]
              chunk_size = settings.streaming_chunk_size  # ex: 1024 chars
              for i in range(0, len(content), chunk_size):
                  chunk = content[i:i+chunk_size]
                  chunks.append({
                      "type": "chunk", 
                      "content": chunk,
                      "offset": i,
                      "length": len(chunk)
                  })
              
              # Page end
              chunks.append({"type": "page_end", "index": page["index"]})
          
          return "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks)
  ```

**Note**: Le chunking permet de:
- Adapter la taille aux context windows des LLM (ex: 1024 tokens ≈ 768 chars)
- Streaming progressif sans attendre toute la page
- Reconstituer le document complet en mémoire si nécessaire

#### `app/converters/docx.py` - DOCX → JSON/JSONL

**Approche**: Chunk textuel par blocs de `CAAS_JSONL_CHUNK_SIZE` caractères (défaut: 1024)

- [ ] **Étape 3.1.8**: Créer modèles Pydantic dans `app/models/response.py`:
  ```python
  class DocxSectionJson(BaseModel):
      index: int
      content: str
      tables: list[list[list[str]]] = []
  
  # Événements JSONL standardisés (cohérents avec tous les convertisseurs)
  class JsonlEvent(BaseModel):
      type: str  # "start", "chunk", "end"
      index: int | None = None
      content: str = ""
      offset: int = 0
      length: int = 0
      metadata: dict = {}
  ```

- [ ] **Étape 3.1.9**: Modifier `_convert_docx()` pour extraire données brutes + Markdown:
  ```python
  def _extract_docx_data(file_bytes: bytes) -> tuple[list[dict], str]:
      # ... extraction existante ...
      sections = [{"index": i, "content": text} for i, text in enumerate(pages)]
      return sections, markdown_text
  ```

- [ ] **Étape 3.1.10**: Ajouter méthode `_to_json()` dans `convert_docx()`:
  ```python
  def convert_docx(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "json":
          sections, _ = _extract_docx_data(file_bytes)
          return {
              "format": "docx", 
              "sections": sections,
              "metadata": {"total_sections": len(sections)}
          }
  ```

- [ ] **Étape 3.1.11**: Ajouter méthode `_to_jsonl()` dans `convert_docx()` avec chunking textuel:
  ```python
  def convert_docx(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "jsonl":
          sections, _ = _extract_docx_data(file_bytes)
          
          chunks = []
          for section in sections:
              # Début section
              chunks.append(JsonlEvent(
                  type="start", 
                  index=section["index"], 
                  metadata={"source": "docx_section"}
              ))
              
              # Chunker le contenu textuel par blocs de CAAS_JSONL_CHUNK_SIZE
              content = section["content"]
              chunk_size = settings.jsonl_chunk_size or 1024
              
              for i in range(0, len(content), chunk_size):
                  chunk_content = content[i:i+chunk_size]
                  chunks.append(JsonlEvent(
                      type="chunk", 
                      content=chunk_content,
                      offset=i,
                      length=len(chunk_content)
                  ))
              
              # Fin section
              chunks.append(JsonlEvent(type="end"))
          
          return "\n".join(json.dumps(e.model_dump(), ensure_ascii=False) for e in chunks)
  ```

**Note**: Le chunking s'applique au contenu textuel (paragraphes, titres). Les tables sont incluses dans le metadata de chaque section.

#### `app/converters/odt.py` - ODT → JSON/JSONL

**Approche**: Chunk textuel par blocs de `CAAS_JSONL_CHUNK_SIZE` caractères (défaut: 1024)

- [ ] **Étape 3.1.11**: Créer modèles Pydantic dans `app/models/response.py`:
  ```python
  class OdtElementJson(BaseModel):
      type: str  # "paragraph", "heading", "list"
      content: str
      level: int = 0
  
  # Événements JSONL standardisés (cohérents avec tous les convertisseurs)
  class JsonlEvent(BaseModel):
      type: str  # "start", "chunk", "end"
      index: int | None = None
      content: str = ""
      offset: int = 0
      length: int = 0
      metadata: dict = {}
  ```

- [ ] **Étape 3.1.12**: Modifier `_convert_odt()` pour extraire éléments bruts + Markdown:
  ```python
  def _extract_odt_data(file_bytes: bytes) -> tuple[list[dict], str]:
      elements = []
      # ... extraction existante ...
      markdown = "# ..."  # conversion Markdown existante
      return elements, markdown
  ```

- [ ] **Étape 3.1.13**: Ajouter méthode `_to_json()` dans `convert_odt()`:
  ```python
  def convert_odt(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "json":
          elements, _ = _extract_odt_data(file_bytes)
          return {
              "format": "odt", 
              "elements": elements,
              "metadata": {"total_elements": len(elements)}
          }
  ```

- [ ] **Étape 3.1.14**: Ajouter méthode `_to_jsonl()` dans `convert_odt()` avec chunking textuel:
  ```python
  def convert_odt(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "jsonl":
          elements, content = _extract_odt_data(file_bytes)
          
          chunks = []
          for i, element in enumerate(elements):
              # Début élément
              chunks.append(JsonlEvent(
                  type="start", 
                  index=i, 
                  metadata={"type": element["type"], "level": element["level"]}
              ))
              
              # Chunker le contenu textuel par blocs de CAAS_JSONL_CHUNK_SIZE
              chunk_size = settings.jsonl_chunk_size or 1024
              
              for j in range(0, len(element["content"]), chunk_size):
                  chunk_content = element["content"][j:j+chunk_size]
                  chunks.append(JsonlEvent(
                      type="chunk", 
                      content=chunk_content,
                      offset=j,
                      length=len(chunk_content)
                  ))
              
              # Fin élément
              chunks.append(JsonlEvent(type="end"))
          
          return "\n".join(json.dumps(e.model_dump(), ensure_ascii=False) for e in chunks)
  ```

**Note**: Le chunking s'applique au contenu textuel de chaque élément (paragraphes, titres, listes).

#### `app/converters/xlsx.py` - XLSX → JSON/JSONL

**Approche**: Une ligne JSONL par ligne de données (données structurées). Chunking optionnel si une ligne dépasse `CAAS_JSONL_CHUNK_SIZE`.

- [ ] **Étape 3.1.14**: Créer modèles Pydantic dans `app/models/response.py`:
  ```python
  class SheetJson(BaseModel):
      name: str
      data: list[list[str]]
      headers: list[str] | None = None
  
  # Événements JSONL standardisés (cohérents avec tous les convertisseurs)
  class JsonlEvent(BaseModel):
      type: str  # "start", "chunk", "row", "end"
      index: int | None = None
      content: str = ""
      offset: int = 0
      length: int = 0
      metadata: dict = {}
  ```

- [ ] **Étape 3.1.15**: Modifier `_convert_xlsx()` pour extraire les feuilles brutes:
  ```python
  def _extract_xlsx_data(file_bytes: bytes) -> list[dict]:
      sheets = []
      for sheet_name, worksheet in workbook.sheetnames.items():
          data = [row for row in worksheet.iter_rows(values_only=True)]
          headers = next(worksheet.row_values(0)) if len(worksheet.row_values(0)) > 0 else None
          sheets.append({"name": sheet_name, "data": data, "headers": headers})
      return sheets
  ```

- [ ] **Étape 3.1.16**: Ajouter méthode `_to_json()` dans `convert_xlsx()`:
  ```python
  def convert_xlsx(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "json":
          sheets = _extract_xlsx_data(file_bytes)
          return {
              "format": "xlsx", 
              "sheets": sheets,
              "metadata": {"total_sheets": len(sheets)}
          }
  ```

- [ ] **Étape 3.1.17**: Ajouter méthode `_to_jsonl()` dans `convert_xlsx()` (une ligne par ligne):
  ```python
  def convert_xlsx(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "jsonl":
          sheets = _extract_xlsx_data(file_bytes)
          
          chunks = []
          for i, sheet in enumerate(sheets):
              # Début feuille
              chunks.append(JsonlEvent(
                  type="start", 
                  index=i, 
                  metadata={"source": f"xlsx_sheet_{sheet['name']}"}
              ))
              
              chunk_size = settings.jsonl_chunk_size or 1024
              
              for j, row in enumerate(sheet["data"]):
                  # Une ligne JSONL par ligne (données structurées)
                  line_content = json.dumps(row, ensure_ascii=False)
                  
                  # Chunking optionnel si la ligne dépasse la taille configurée
                  if len(line_content) > chunk_size:
                      for k in range(0, len(line_content), chunk_size):
                          chunks.append(JsonlEvent(
                              type="chunk", 
                              content=line_content[k:k+chunk_size],
                              offset=k,
                              length=len(line_content[k:k+chunk_size])
                          ))
                  else:
                      chunks.append(JsonlEvent(type="row", data=row))
              
              # Fin feuille
              chunks.append(JsonlEvent(type="end"))
          
          return "\n".join(json.dumps(e.model_dump(), ensure_ascii=False) for e in chunks)
  ```

**Note**: Pour XLSX/ODS (données structurées), le chunking est optionnel et désactivé par défaut. Une ligne JSONL par ligne de données est la norme, avec chunking uniquement si nécessaire pour des lignes très longues (> 1024 chars).

#### `app/converters/ods.py` - ODS → JSON/JSONL

**Approche**: Une ligne JSONL par ligne de données (données structurées). Chunking optionnel si une ligne dépasse `CAAS_JSONL_CHUNK_SIZE`.

- [ ] **Étape 3.1.17**: Créer modèles Pydantic dans `app/models/response.py`:
  ```python
  class OdsCellJson(BaseModel):
      row: int
      col: int
      value: str | float | None
  
  # Événements JSONL standardisés (cohérents avec tous les convertisseurs)
  class JsonlEvent(BaseModel):
      type: str  # "start", "chunk", "row", "end"
      index: int | None = None
      content: str = ""
      offset: int = 0
      length: int = 0
      metadata: dict = {}
  ```

- [ ] **Étape 3.1.18**: Modifier `_convert_ods()` pour extraire les cellules brutes:
  ```python
  def _extract_ods_data(file_bytes: bytes) -> list[dict]:
      cells = []
      # ... extraction existante ...
      return cells
  ```

- [ ] **Étape 3.1.19**: Ajouter méthode `_to_json()` dans `convert_ods()`:
  ```python
  def convert_ods(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "json":
          cells, _ = _extract_ods_data(file_bytes)
          return {
              "format": "ods", 
              "cells": cells,
              "metadata": {"total_cells": len(cells)}
          }
  ```

- [ ] **Étape 3.1.20**: Ajouter méthode `_to_jsonl()` dans `convert_ods()` (une ligne par ligne):
  ```python
  def convert_ods(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "jsonl":
          sheets, _ = _extract_ods_data(file_bytes)
          
          chunks = []
          for i, sheet in enumerate(sheets):
              # Début feuille
              chunks.append(JsonlEvent(
                  type="start", 
                  index=i, 
                  metadata={"source": f"ods_sheet_{sheet['name']}"}
              ))
              
              chunk_size = settings.jsonl_chunk_size or 1024
              
              for j, row in enumerate(sheet["data"]):
                  # Une ligne JSONL par ligne (données structurées)
                  line_content = json.dumps(row, ensure_ascii=False)
                  
                  # Chunking optionnel si la ligne dépasse la taille configurée
                  if len(line_content) > chunk_size:
                      for k in range(0, len(line_content), chunk_size):
                          chunks.append(JsonlEvent(
                              type="chunk", 
                              content=line_content[k:k+chunk_size],
                              offset=k,
                              length=len(line_content[k:k+chunk_size])
                          ))
                  else:
                      chunks.append(JsonlEvent(type="row", data=row))
              
              # Fin feuille
              chunks.append(JsonlEvent(type="end"))
          
          return "\n".join(json.dumps(e.model_dump(), ensure_ascii=False) for e in chunks)
  ```

**Note**: Pour ODS (données structurées), le chunking est optionnel et désactivé par défaut. Une ligne JSONL par ligne de données est la norme, avec chunking uniquement si nécessaire pour des lignes très longues (> 1024 chars).
      content: str
      offset: int = 0
      length: int = 0
  ```
- [ ] **Étape 3.1.18**: Modifier `_convert_ods()` pour extraire les cellules brutes:
  ```python
  def _extract_ods_data(file_bytes: bytes) -> list[dict]:
      cells = []
      # ... extraction existante ...
      return cells
  ```
- [ ] **Étape 3.1.19**: Ajouter méthodes `_to_json()` et `_to_jsonl()` dans `convert_ods()`:
  ```python
  def convert_ods(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "json":
          cells = _extract_ods_data(file_bytes)
          return {"format": "json", "cells": cells}
      elif format == "jsonl":
          # Option A: Une ligne JSONL par feuille (pour données structurées)
          chunks = []
          for i, sheet in enumerate(sheets):
              chunks.append({"type": "sheet_start", "index": i})
              
              # Chunk les lignes si nécessaire
              chunk_size = settings.streaming_chunk_size
              for j, row in enumerate(sheet["data"]):
                  line_content = json.dumps(row, ensure_ascii=False)
                  if len(line_content) > chunk_size:
                      for k in range(0, len(line_content), chunk_size):
                          chunks.append({
                              "type": "chunk", 
                              "content": line_content[k:k+chunk_size],
                              "offset": k,
                              "length": len(line_content[k:k+chunk_size])
                          })
                  else:
                      chunks.append({"type": "row", "index": j, "data": row})
              
              chunks.append({"type": "sheet_end", "index": i})
          
          return "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks)
  ```

#### `app/converters/pptx.py` - PPTX → JSON/JSONL

**Approche**: Chunk textuel par diapositive (comme PDF/DOCX). Chaque diapositive est chunkée en blocs de `CAAS_JSONL_CHUNK_SIZE`.

- [ ] **Étape 3.1.20**: Créer modèles Pydantic dans `app/models/response.py`:
  ```python
  class SlideJson(BaseModel):
      index: int
      title: str | None = None
      content: list[str]
      tables: list[list[list[str]]] = []
  
  # Événements JSONL standardisés (cohérents avec tous les convertisseurs)
  class JsonlEvent(BaseModel):
      type: str  # "start", "chunk", "end"
      index: int | None = None
      content: str = ""
      offset: int = 0
      length: int = 0
      metadata: dict = {}
  ```

- [ ] **Étape 3.1.21**: Modifier `_convert_pptx()` pour extraire les diapositives brutes:
  ```python
  def _extract_pptx_data(file_bytes: bytes) -> list[dict]:
      slides = []
      # ... extraction existante ...
      return slides
  ```

- [ ] **Étape 3.1.22**: Ajouter méthode `_to_json()` dans `convert_pptx()`:
  ```python
  def convert_pptx(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "json":
          slides, _ = _extract_pptx_data(file_bytes)
          return {
              "format": "pptx", 
              "slides": slides,
              "metadata": {"total_slides": len(slides)}
          }
  ```

- [ ] **Étape 3.1.23**: Ajouter méthode `_to_jsonl()` dans `convert_pptx()` (chunk textuel):
  ```python
  def convert_pptx(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "jsonl":
          slides, _ = _extract_pptx_data(file_bytes)
          
          chunks = []
          for i, slide in enumerate(slides):
              # Début diapositive
              chunks.append(JsonlEvent(
                  type="start", 
                  index=i, 
                  metadata={"source": f"pptx_slide_{slide.get('title', '')}"}
              ))
              
              chunk_size = settings.jsonl_chunk_size or 1024
              
              # Chunker le contenu textuel de la diapositive
              content_text = " ".join(slide.get("content", []))
              for j in range(0, len(content_text), chunk_size):
                  chunks.append(JsonlEvent(
                      type="chunk", 
                      content=content_text[j:j+chunk_size],
                      offset=j,
                      length=len(content_text[j:j+chunk_size])
                  ))
              
              # Fin diapositive
              chunks.append(JsonlEvent(type="end"))
          
          return "\n".join(json.dumps(e.model_dump(), ensure_ascii=False) for e in chunks)
  ```

**Note**: Pour PPTX (données textuelles), le chunking est activé par défaut avec `CAAS_JSONL_CHUNK_SIZE` (défaut: 1024 caractères).
  
  # Pour JSONL streaming avec chunking
  class JsonlChunk(BaseModel):
      type: str  # "slide_start", "chunk", "slide_end"
      slide_index: int | None = None
      content: str
      offset: int = 0
      length: int = 0
  ```
- [ ] **Étape 3.1.21**: Modifier `_convert_pptx()` pour extraire les diapositives brutes:
  ```python
  def _extract_pptx_data(file_bytes: bytes) -> list[dict]:
      slides = []
      # ... extraction existante ...
      return slides
  ```
- [ ] **Étape 3.1.22**: Ajouter méthodes `_to_json()` et `_to_jsonl()` dans `convert_pptx()`:
  ```python
  def convert_pptx(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "json":
          slides = _extract_pptx_data(file_bytes)
          return {"format": "json", "slides": slides}
      elif format == "jsonl":
          chunks = []
          for i, slide in enumerate(slides):
              # Slide start
              chunks.append({"type": "slide_start", "index": i})
              
              # Chunk the content
              content = json.dumps(slide, ensure_ascii=False)
              chunk_size = settings.streaming_chunk_size  # ex: 1024 chars
              for j in range(0, len(content), chunk_size):
                  chunk = content[j:j+chunk_size]
                  chunks.append({
                      "type": "chunk", 
                      "content": chunk,
                      "offset": j,
                      "length": len(chunk)
                  })
              
              # Slide end
              chunks.append({"type": "slide_end", "index": i})
          
          return "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks)
  ```

#### `app/converters/odp.py` - ODP → JSON/JSONL
- [ ] **Étape 3.1.23**: Créer modèle Pydantic `OdpSlideJson`:
  ```python
  class OdpSlideJson(BaseModel):
      index: int
      title: str | None = None
      content: list[str]
      lists: list[list[str]] = []
  
  # Pour JSONL streaming avec chunking
  class JsonlChunk(BaseModel):
      type: str  # "slide_start", "chunk", "slide_end"
      slide_index: int | None = None
      content: str
      offset: int = 0
      length: int = 0
  ```
- [ ] **Étape 3.1.24**: Modifier `_convert_odp()` pour extraire les slides brutes:
  ```python
  def _extract_odp_data(file_bytes: bytes) -> list[dict]:
      slides = []
      # ... extraction existante ...
      return slides
  ```
- [ ] **Étape 3.1.25**: Ajouter méthodes `_to_json()` et `_to_jsonl()` dans `convert_odp()`:
  ```python
  def convert_odp(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "json":
          slides = _extract_odp_data(file_bytes)
          return {"format": "json", "slides": slides}
      elif format == "jsonl":
          chunks = []
          for i, slide in enumerate(slides):
              # Slide start
              chunks.append({"type": "slide_start", "index": i})
              
              # Chunk the content
              content = json.dumps(slide, ensure_ascii=False)
              chunk_size = settings.streaming_chunk_size  # ex: 1024 chars
              for j in range(0, len(content), chunk_size):
                  chunk = content[j:j+chunk_size]
                  chunks.append({
                      "type": "chunk", 
                      "content": chunk,
                      "offset": j,
                      "length": len(chunk)
                  })
              
              # Slide end
              chunks.append({"type": "slide_end", "index": i})
          
          return "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks)
  ```

#### `app/converters/html.py` - HTML → JSON/JSONL

**Approche**: Chunk textuel par élément HTML (comme PDF/PPTX/ODP). Chaque élément est chunké en blocs de `CAAS_JSONL_CHUNK_SIZE`.

- [ ] **Étape 3.1.26**: Créer modèles Pydantic dans `app/models/response.py`:
  ```python
  class HtmlElementJson(BaseModel):
      tag: str
      content: str
      attributes: dict[str, str] = {}
      children: list[dict] = []
  
  # Événements JSONL standardisés (cohérents avec tous les convertisseurs)
  class JsonlEvent(BaseModel):
      type: str  # "start", "chunk", "end"
      index: int | None = None
      content: str = ""
      offset: int = 0
      length: int = 0
      metadata: dict = {}
  ```

- [ ] **Étape 3.1.27**: Modifier `_convert_html()` pour extraire les éléments bruts:
  ```python
  def _extract_html_data(file_bytes: bytes) -> list[dict]:
      elements = []
      # ... extraction existante avec BeautifulSoup ...
      return elements
  ```

- [ ] **Étape 3.1.28**: Ajouter méthode `_to_json()` dans `convert_html()`:
  ```python
  def convert_html(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "json":
          elements, _ = _extract_html_data(file_bytes)
          return {
              "format": "html", 
              "elements": elements,
              "metadata": {"total_elements": len(elements)}
          }
  ```

- [ ] **Étape 3.1.29**: Ajouter méthode `_to_jsonl()` dans `convert_html()` (chunk textuel):
  ```python
  def convert_html(file_bytes: bytes, format: str = "markdown") -> dict | str:
      if format == "jsonl":
          elements, _ = _extract_html_data(file_bytes)
          
          chunks = []
          for i, element in enumerate(elements):
              # Début élément HTML
              chunks.append(JsonlEvent(
                  type="start", 
                  index=i, 
                  metadata={"tag": element.get("tag", ""), "attributes": str(element.get("attributes", {}))}
              ))
              
              chunk_size = settings.jsonl_chunk_size or 1024
              
              # Chunker le contenu textuel de l'élément HTML
              content_text = element.get("content", "")
              for j in range(0, len(content_text), chunk_size):
                  chunks.append(JsonlEvent(
                      type="chunk", 
                      content=content_text[j:j+chunk_size],
                      offset=j,
                      length=len(content_text[j:j+chunk_size])
                  ))
              
              # Fin élément HTML
              chunks.append(JsonlEvent(type="end"))
          
          return "\n".join(json.dumps(e.model_dump(), ensure_ascii=False) for e in chunks)
  ```

**Note**: Pour HTML (données textuelles), le chunking est activé par défaut avec `CAAS_JSONL_CHUNK_SIZE` (défaut: 1024 caractères).

### Configuration recommandée dans `pyproject.toml` ou `config.py`:

```python
# Dans app/config.py ou pyproject.toml
JSONL_CHUNK_SIZE = 1024  # Taille par défaut des chunks en caractères
ENABLE_JSONL_CHUNKING = True  # Activer le chunking pour les fichiers textuels
```

**Pourquoi cette approche?**
- **Textuel (PDF/DOCX/PPTX/HTML)**: Chunking activé → optimisé pour context windows LLM
- **Structuré (XLSX/ODS)**: Pas de chunking par défaut → une ligne JSONL par ligne de données, plus lisible et facile à parser

---

### 3.2 Modifier l'orchestrateur de conversion

**Objectif**: Mettre à jour `app/converter.py` pour supporter les nouveaux formats.

**Actions**:
- [ ] **Étape 3.2.1**: Importer le module des modèles:
  ```python
  from app.models.response import ConversionResponse, PageJson
  ```
- [ ] **Étape 3.2.2**: Ajouter paramètre `format` à la fonction principale:
  ```python
  def convert_file(file_bytes: bytes, file_type: str, format: str = "markdown") -> dict | str:
      # ... logique existante ...
  ```
- [ ] **Étape 3.2.3**: Modifier le routage vers les convertisseurs:
  ```python
  if format == "json":
      return converter.convert(file_bytes, file_type, format="json")
  elif format == "jsonl":
      return converter.convert(file_bytes, file_type, format="jsonl")
  else:
      # Défaut: markdown
      return converter.convert(file_bytes, file_type)
  ```

---

### 3.3 Modifier le streaming pour JSON/JSONL

**Objectif**: Adapter `app/streaming.py` pour supporter le streaming JSON.

**Actions**:
- [ ] **Étape 3.3.1**: Créer modèle Pydantic `StreamingEventJson`:
  ```python
  class StreamingEventJson(BaseModel):
      type: str  # "page", "complete", "error"
      page_index: int | None = None
      content: dict | str
  ```
- [ ] **Étape 3.3.2**: Modifier `_convert_pdf_stream()` pour JSON:
  ```python
  async def _convert_pdf_stream(file_bytes, format="markdown"):
      if format == "json":
          _, json_pages = _extract_pdf_content(file_bytes)
          for page in json_pages:
              yield {"type": "page", "content": page}
          yield {"type": "complete"}
  ```
- [ ] **Étape 3.3.3**: Modifier `_convert_pdf_stream()` pour JSONL:
  ```python
  async def _convert_pdf_stream(file_bytes, format="markdown"):
      if format == "jsonl":
          _, json_pages = _extract_pdf_content(file_bytes)
          for page in json_pages:
              yield {"type": "page", "content": json.dumps(page)}
          yield {"type": "complete"}
  ```

---

### 3.4 Mettre à jour les routes

**Objectif**: Modifier `app/routes/convert.py` pour accepter le paramètre format.

**Actions**:
- [ ] **Étape 3.4.1**: Ajouter validation du paramètre format:
  ```python
  from typing import Literal
  
  def convert_endpoint(file, format: str = "markdown"):
      if format not in ["markdown", "json", "jsonl"]:
          raise HTTPException(status_code=400, detail="Format invalide")
  ```
- [ ] **Étape 3.4.2**: Modifier l'appel au convertisseur:
  ```python
  result = converter.convert_file(file_bytes, file_type, format=format)
  
  if format == "jsonl":
      return Response(content=result, media_type="text/plain; charset=utf-8")
  else:
      return JSONResponse(content=ConversionResponse(format=format, content=result))
  ```

---

---

### 3.2 Modifier le orchestrateur de conversion

**Objectif**: Mettre à jour `app/converter.py` pour supporter les nouveaux formats.

**Actions**:
- [ ] Ajouter paramètre `format: Literal["markdown", "json", "jsonl"] = "markdown"`
- [ ] Modifier la logique de routage vers les convertisseurs
- [ ] Pour JSON/JSONL, appeler les nouvelles méthodes des convertisseurs
- [ ] Gérer le cas où aucun format n'est spécifié (défaut: markdown)

---

### 3.3 Modifier le streaming pour JSON/JSONL

**Objectif**: Adapter `app/streaming.py` pour supporter le streaming JSON.

**Actions**:
- [ ] Ajouter support de streaming pour format JSON (chunks de pages)
- [ ] Ajouter support de streaming pour format JSONL (une ligne par événement SSE)
- [ ] Modifier `_convert_pdf_stream()` et autres méthodes de streaming
- [ ] Pour JSON: envoyer des événements avec le chunk JSON complet
- [ ] Pour JSONL: envoyer une ligne JSON par événement SSE

---

### 3.4 Mettre à jour les routes

**Objectif**: Modifier `app/routes/convert.py` pour accepter le paramètre format.

**Actions**:
- [ ] Ajouter `format=markdown|json|jsonl` aux endpoints `/convert` et `/convert/batch`
- [ ] Passer le format au convertisseur
- [ ] Gérer les réponses JSON vs Markdown dans la réponse HTTP
- [ ] Pour JSONL: retourner `text/plain; charset=utf-8` avec une ligne par ligne

---

## 4. Tests unitaires et d'intégration

### 4.1 Créer des fixtures de test

**Objectif**: Préparer les données de test pour les nouveaux formats.

**Actions**:
- [ ] Dans `tests/conftest.py`: ajouter fixtures pour JSON/JSONL
- [ ] Créer fixture `sample_pdf_bytes` (déjà existant)
- [ ] Créer fixture `expected_json_output` pour chaque type de fichier
- [ ] Créer fixture `expected_jsonl_output` pour chaque type de fichier

---

### 4.2 Tests unitaires des convertisseurs JSON

**Objectif**: Tester la conversion vers JSON/JSONL pour chaque format.

**Actions**:

#### `tests/test_converter.py` (ou créer `tests/test_converter_json.py`)
- [ ] Test: PDF → JSON (structure correcte)
- [ ] Test: PDF → JSONL (une ligne par page)
- [ ] Test: DOCX → JSON
- [ ] Test: ODT → JSON
- [ ] Test: XLSX → JSON (multi-feuille)
- [ ] Test: ODS → JSON
- [ ] Test: PPTX → JSON
- [ ] Test: ODP → JSON
- [ ] Test: HTML → JSON

**Exemple de test**:
```python
def test_pdf_to_json(sample_pdf_bytes):
    result = convert_file(sample_pdf_bytes, format="json")
    
    assert "format" in result
    assert result["format"] == "json"
    assert "pages" in result or "content" in result
    
    if "pages" in result:
        assert isinstance(result["pages"], list)
        assert len(result["pages"]) > 0
        page = result["pages"][0]
        assert "index" in page
        assert "content" in page
```

---

### 4.3 Tests unitaires des convertisseurs JSONL

**Objectif**: Tester la conversion vers JSONL pour chaque format.

**Actions**:
- [ ] Test: PDF → JSONL (validation du format ligne par ligne)
- [ ] Test: DOCX → JSONL
- [ ] ... (pour tous les formats)

---

### 4.4 Tests d'intégration des endpoints

**Objectif**: Tester les routes avec le paramètre format.

**Actions**:
- [ ] Dans `tests/test_endpoints.py`: ajouter tests pour `/convert?format=json`
- [ ] Ajouter tests pour `/convert?format=jsonl`
- [ ] Ajouter tests pour `/convert/batch?format=json`
- [ ] Vérifier les codes de réponse HTTP (200, 4xx, 5xx)
- [ ] Vérifier le contenu du body JSON

---

### 4.5 Tests de streaming JSON/JSONL

**Objectif**: Tester le streaming pour les grands documents.

**Actions**:
- [ ] Test: PDF grand → streaming JSON (SSE events)
- [ ] Test: PDF grand → streaming JSONL (une ligne par événement)
- [ ] Vérifier que tous les événements sont envoyés
- [ ] Vérifier l'ordre des événements

---

## 5. Documentation (README.md)

### 5.1 Mettre à jour la section Features

**Objectif**: Documenter le nouveau support JSON/JSONL dans README.md.

**Actions**:
- [ ] Dans "Conversion", ajouter:
  ```markdown
  - **Export formats**: Markdown (défaut), JSON, JSONL
  - **Streaming support**: SSE pour JSON et JSONL sur grands documents
  ```
- [ ] Ajouter un exemple de sortie JSON dans la section Features

---

### 5.2 Mettre à jour la section Usage/API Reference

**Objectif**: Documenter l'utilisation des nouveaux formats.

**Actions**:
- [ ] Dans "Usage", ajouter:
  ```bash
  # Export en JSON
  curl -X POST "http://localhost:8000/convert" \
       -H "Content-Type: multipart/form-data" \
       -F "file=@document.pdf" \
       -F "format=json"

  # Export en JSONL (une ligne par page)
  curl -X POST "http://localhost:8000/convert?streaming=true&format=jsonl" \
       -H "Content-Type: multipart/form-data" \
       -F "file=@document.pdf"
  ```

- [ ] Ajouter un exemple de sortie JSON dans la documentation
- [ ] Ajouter un exemple de sortie JSONL

---

### 5.3 Mettre à jour l'architecture diagram

**Objectif**: Mettre à jour le diagramme d'architecture.

**Actions**:
- [ ] Dans "Architecture", ajouter:
  ```
  Convertisseur Markdown → Convertisseur JSON/JSONL
  ```
- [ ] Ajouter un nouveau diagramme pour le flux JSON

---

## 6. Changelog (CHANGELOG.md)

### 6.1 Ajouter une section dans [Unreleased]

**Objectif**: Documenter les changements à venir.

**Actions**:
- [ ] Dans `CHANGELOG.md`, sous `[Unreleased]`:
  ```markdown
  ### Added
  
  - **Export JSON/JSONL**: nouvelle option pour exporter les conversions en format JSON ou JSONL
    - Paramètre `format=json` retourne un objet JSON structuré avec toutes les pages
    - Paramètre `format=jsonl` retourne une ligne JSON par page (idéal pour grands documents)
    - Streaming SSE supporté pour JSON et JSONL sur PDF, DOCX, ODT, XLSX, PPTX, HTML
  - **Modèles Pydantic**: nouveaux modèles de réponse dans `app/models/response.py`
  
  ### Changed
  
  - Endpoint `/convert` accepte maintenant le paramètre `format=markdown|json|jsonl` (défaut: markdown)
  ```

---

## 7. Tests E2E et validation

### 7.1 Tests de bout en bout

**Objectif**: Tester les flux complets avec différents formats.

**Actions**:
- [ ] Script bash/Python pour tester chaque format sur un fichier réel
- [ ] Comparer la taille des sorties (Markdown vs JSON vs JSONL)
- [ ] Vérifier que toutes les données sont présentes dans le JSON

---

### 7.2 Performance benchmarks

**Objectif**: Mesurer l'impact de l'ajout JSON/JSONL sur les performances.

**Actions**:
- [ ] Benchmark: conversion Markdown seule (baseline)
- [ ] Benchmark: conversion JSON pour un document moyen
- [ ] Benchmark: conversion JSONL pour un grand document
- [ ] Comparer le temps d'exécution et la taille des sorties

---

### 7.3 Validation de régression

**Objectif**: S'assurer que Markdown (défaut) fonctionne toujours correctement.

**Actions**:
- [ ] Lancer tous les tests existants (`pytest`)
- [ ] Vérifier que le format markdown par défaut n'a pas changé
- [ ] S'assurer que les tests de sécurité fonctionnent pour tous les formats

---

## ✅ Checklist de validation finale

- [ ] Tous les convertisseurs supportent `format=json`
- [ ] Tous les convertisseurs supportent `format=jsonl`
- [ ] Le streaming fonctionne pour JSON et JSONL
- [ ] Les tests unitaires passent (100% coverage souhaité)
- [ ] Les tests d'intégration passent
- [ ] La documentation README.md est à jour
- [ ] Le CHANGELOG.md est mis à jour
- [ ] Les benchmarks sont documentés
- [ ] Aucune régression sur le format Markdown par défaut

---

## 🔄 Plan de rollback (si problème)

Si une étape échoue, revenir en arrière:

1. **Problème dans un convertisseur**: 
   - Commit séparé pour chaque convertisseur
   - Rollback facile avec `git revert` du commit spécifique

2. **Problème d'API**:
   - Le paramètre format est optionnel (défaut: markdown)
   - Si cassure, retirer le paramètre et revenir à l'ancien comportement

3. **Problème de tests**:
   - Les nouveaux tests sont dans des fichiers séparés ou sections distinctes
   - Possibilité de désactiver les nouveaux tests temporairement

---

## 📝 Notes d'implémentation

- **Priorité**: Commencer par PDF (le plus complexe), puis les autres formats
- **Pattern**: Utiliser le même pattern pour tous les convertisseurs (cohérence)
- **Backward compatibility**: Le format Markdown reste la valeur par défaut
- **Performance**: JSONL est préférable pour les grands documents (> 10 pages)
