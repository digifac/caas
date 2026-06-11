# TODO: Add JSON/JSONL conversion

This file lists the steps to add support for JSON and JSONL export to existing conversions (currently Markdown). Each step is short, simple, and reversible.

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

**Objectif**: Identifier comment les convertisseurs Markdown sont implémentés pour réutiliser le pattern. ✅ **COMPLÉTÉ**

**Actions réalisées**:
- [x] Read `app/converters/base.py` - shared utilities (`clean_lines`, heading detection, lists)
- [x] Examiner `app/converters/pdf.py` - convertisseur PDF → Markdown avec OCR et extraction de liens
- [x] Vérifier la structure des données retournées par chaque convertisseur

**Structure de données découverte**:
```python
# Internal format used by all converters:
results = [(page_idx, markdown_text, urls)]  # tuple (page_index, markdown_text, url_list)

# Exemple PDF:
def _extract_pdf_content(file_bytes: bytes) -> list[tuple[int, str, list[str]]]:
    """Returns a list of tuples (page_idx, page_md, [urls])""
```

**Format de sortie actuel**:
- Markdown en chaîne unique retournée par `convert_pdf_to_md()`
- Format: `"\n\n".join(md_blocks).replace("\n\n\n", "\n\n").strip()`
- Les liens sont ajoutés comme `[uri](uri)` à la fin du markdown

**Identified pattern for reuse**:
1. Extract raw data → list of tuples `(page_idx, content, metadata)`
2. Clean and convert to Markdown via `clean_lines()`
3. Final aggregation into single string

**Référence**: 
- `app/converters/base.py` - utilitaires communs (`clean_lines`, `is_uppercase_heading`)
- `app/converters/pdf.py` - exemple complet PDF → Markdown avec streaming async
- `app/streaming.py` - implémentation du streaming SSE

---

### 1.2 Analyser les données de sortie ✅ **COMPLÉTÉ**

**Objectif**: Comprendre la structure des données brutes avant conversion en Markdown.

**Actions réalisées**:
- [x] Pour PDF: identifier la structure `(page_idx, markdown_text, urls)` via `_extract_pdf_content()`
- [x] For DOCX: returns a raw Markdown string via `mammoth.convert_to_markdown()`
- [x] For ODT: returns a list of lines `lines: list[str]` with list handling
- [x] For XLSX: returns a Markdown string with tables via `_build_sheet_md()`
- [x] For PPTX: returns a list of lines `all_lines` with separators between slides
- [x] Pour HTML: utilise BeautifulSoup + html2text pour conversion directe en Markdown
- [x] Pour ODP: retourne une chaîne Markdown via `clean_lines(all_lines)`

**Structures de données découvertes**:

| Converteur | Structure brute | Type | Description |
|------------|-----------------|------|-------------|
| PDF | `list[tuple[int, str, list[str]]]` | List of tuples | `(page_idx, markdown_text, [urls])` per page |
| DOCX | `str` | Markdown string | Raw mammoth result with links/images |
| ODT | `list[str]` | List of lines | Paragraphs and lists, joined with `\n`.join(lines) |
| XLSX | `str` | Chaîne Markdown | Tableaux par feuille, séparés par `---` |
| PPTX | `list[str]` | List of lines | Titles, paragraphs, tables with `---` between slides |
| HTML | `str` | Markdown string | html2text result + post-processing BeautifulSoup |
| ODP | `str` | Markdown string | Content of text frames via clean_lines() |
| ODS | `list[str]` | List of lines | Tables per sheet, separated by `---`, empty cell handling |

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

**Pattern unifié pour tous les convertisseurs**:
1. **PDF/ODT/PPTX/HTML/ODP**: Extraction → Liste structurée → Nettoyage → Agrégation en Markdown
2. **DOCX/XLSX**: Conversion directe en chaîne Markdown (pas de liste intermédiaire)

**Adaptations nécessaires pour JSON/JSONL**:
- PDF: Utiliser directement la structure `(page_idx, content, urls)` existante ✅
- DOCX: Wrapper autour du résultat mammoth avec indexation implicite par ordre d'apparition
- ODT/XLSX/PPTX/HTML/ODP/ODS: Transformer la liste de lignes en blocs logiques (paragraphes, tableaux)

---

## 2. Conception de l'API

### 2.1 Définir les endpoints

**Objectif**: Ajouter des paramètres d'export au endpoint existant `/convert`. ✅ **COMPLÉTÉ**

**Actions réalisées**:
- [x] Ajouter `?format=json` ou `?format=markdown|json|jsonl` à `/convert`
- [x] Ajouter `?format=jsonl` pour le format JSONL
- [x] Définir la réponse par défaut (Markdown) si aucun format non spécifié

**Changement attendu**:
```python
# Actuel
GET /convert?file=... → Markdown string

# Nouveau
GET /convert?file=&format=markdown → Markdown string (défaut)
GET /convert?file=&format=json → JSON object
GET /convert?file=&format=jsonl → JSONL stream (SSE ou raw text)
```

**Paramètres d'endpoint**:
| Paramètre | Type | Valeurs possibles | Défaut | Description |
|-----------|------|-------------------|--------|-------------|
| `format` | query string | `"markdown"`, `"json"`, `"jsonl"` | `"markdown"` | Format de sortie souhaité |

**Comportement par format**:
- **Markdown (default)**: Returns a raw Markdown string
- **JSON**: Returns a structured JSON object with metadata and paginated content
- **JSONL**: Returns raw text with one JSON line per event (for streaming)

**Exemples d'utilisation**:
```bash
# Export en Markdown (défaut)
curl -X POST "http://localhost:8000/convert" \
     -F "file=@document.pdf"

# Export en JSON structuré
curl -X POST "http://localhost:8000/convert?format=json" \
     -F "file=@document.pdf"

# Export en JSONL (streaming)
curl -X POST "http://localhost:8000/convert?format=jsonl" \
     -F "file=@document.pdf"
```

**Réponse HTTP**:
- **Markdown**: `text/plain; charset=utf-8` avec le contenu Markdown
- **JSON**: `application/json` avec l'objet JSON structuré
- **JSONL**: `text/plain; charset=utf-8` avec une ligne JSON par événement (pour streaming) ou `application/x-ndjson`

**Validation du paramètre format**:
```python
from typing import Literal

def convert_endpoint(file, format: str = "markdown"):
    if format not in ["markdown", "json", "jsonl"]:
        raise HTTPException(status_code=400, detail="Format invalide. Doit être 'markdown', 'json' ou 'jsonl'.")
```

**Notes d'implémentation**:
- Le paramètre `format` est optionnel et par défaut retourne Markdown (comportement existant)
- Pour JSONL en streaming, chaque événement SSE correspond à une ligne JSON complète
- Pour JSON non-streaming, la réponse contient tout le document dans un objet JSON unique

---

### 2.2 Définir le contrat de réponse JSON

**Objectif**: Spécifier la structure exacte du JSON retourné pour tous les convertisseurs. ✅ **COMPLÉTÉ**

**Actions réalisées**:
- [x] Créer un modèle Pydantic pour la réponse JSON (`app/models/response.py`)
- [x] Inclure: `format`, `pages` (ou `content`), `metadata`, `request_id`
- [x] Définir les champs optionnels et leurs types

**Modèles Pydantic définis**:

#### 1. Modèle principal de réponse JSON (`app/models/response.py`)
```python
from pydantic import BaseModel, Field
from typing import Union, Optional, List, Dict, Any
from datetime import datetime

class PageJson(BaseModel):
    """Représente une page ou unité logique du document."""
    index: int = Field(..., description="Page/section index")
    content: str = Field(..., description="Raw content (Markdown or text)")
    urls: List[str] = Field(default_factory=list, description="Liens extraits")

class ConversionResponse(BaseModel):
    """Réponse JSON structurée pour l'API de conversion."""
    format: str = Field("json", description="Format de sortie ('pdf', 'docx', etc.)")
    pages: List[PageJson] = Field(default_factory=list, description="Liste des pages/sections")
    content: Optional[str] = Field(None, description="Raw Markdown content (alternative to pages)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées du document")
    request_id: Optional[str] = Field(None, description="ID de la requête pour le tracing")
    success: bool = Field(True, description="Statut de réussite")
    timestamp: datetime = Field(default=datetime.utcnow(), description="Horodatage")
```

#### 2. Modèle JSONL standardisé (`app/models/response.py`)
```python
class JsonlEvent(BaseModel):
    """Événement JSONL pour le streaming granulaire."""
    type: str = Field(..., pattern="^(start|chunk|end)$", description="Type d'événement")
    index: Optional[int] = Field(None, description="Page/section index")
    content: str = Field("", description="Chunk content")
    offset: int = Field(0, description="Décalage dans le document")
    length: int = Field(0, description="Longueur du chunk")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées")

class JsonlStartEvent(JsonlEvent):
    """Événement de début de document."""
    type: str = "start"
    
class JsonlChunkEvent(JsonlEvent):
    """Content chunk event."""
    type: str = "chunk"
    
class JsonlEndEvent(JsonlEvent):
    """Événement de fin de document."""
    type: str = "end"
```

**Structure complète du JSON retourné**:

#### Format pour PDF (exemple complet):
```json
{
  "format": "pdf",
  "pages": [
    {
      "index": 0,
      "content": "# Titre de la page\n\nContenu de la première page...",
      "urls": ["https://example.com/link1"]
    },
    {
      "index": 1,
      "content": "# Deuxième page\n\nPlus de contenu ici...",
      "urls": []
    }
  ],
  "metadata": {
    "total_pages": 2,
    "file_size_bytes": 1048576,
    "created_at": "2026-06-11T10:30:00Z",
    "title": "Document PDF"
  },
  "request_id": "req_abc123xyz",
  "success": true,
  "timestamp": "2026-06-11T10:30:05.123456Z"
}
```

#### Format pour DOCX (exemple):
```json
{
  "format": "docx",
  "pages": [
    {
      "index": 0,
      "content": "# Titre du document\n\nIntroduction...",
      "urls": []
    }
  ],
  "metadata": {
    "total_pages": 1,
    "word_count": 250,
    "paragraphs": 5,
    "author": "Jean Dupont"
  },
  "request_id": "req_def456uvw",
  "success": true,
  "timestamp": "2026-06-11T10:30:05.234567Z"
}
```

#### Format pour XLSX (exemple):
```json
{
  "format": "xlsx",
  "pages": [
    {
      "index": 0,
      "content": "| Nom | Prénom | Âge |\n|-----|--------|-----|\n| Jean | Dupont | 30 |",
      "urls": []
    }
  ],
  "metadata": {
    "total_pages": 1,
    "sheets": ["Feuil1"],
    "rows_count": 4,
    "columns_count": 3
  },
  "request_id": "req_ghi789rst",
  "success": true,
  "timestamp": "2026-06-11T10:30:05.345678Z"
}
```

**Champs obligatoires vs optionnels**:

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `format` | str | ✅ Oui | Format source du document (pdf, docx, xlsx, etc.) |
| `pages` | List[PageJson] | ✅ Oui | Liste des pages/sections avec contenu |
| `content` | Optional[str] | ❌ Non | Alternative pour les formats simples (DOCX) |
| `metadata` | Dict[str, Any] | ✅ Oui (vide par défaut) | Métadonnées spécifiques au format |
| `request_id` | Optional[str] | ❌ Non | ID unique de la requête |
| `success` | bool | ✅ Oui (True par défaut) | Statut de réussite |
| `timestamp` | datetime | ✅ Oui | Horodatage UTC |

**Validation des données**:
```python
from pydantic import ValidationError, field_validator

class ConversionResponse(BaseModel):
    # ... autres champs ...
    
    @field_validator('pages')
    def validate_pages(cls, v: List[PageJson]) -> List[PageJson]:
        if not v:
            raise ValueError("Le champ 'pages' ne peut pas être vide")
        for i, page in enumerate(v):
            if not page.content.strip():
                raise ValueError(f"Page {i} must contain non-empty content")
        return v
    
    @field_validator('metadata')
    def validate_metadata(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        # Validation optionnelle des métadonnées selon le format
        if 'total_pages' in v and isinstance(v['total_pages'], int):
            if v['total_pages'] < 1:
                raise ValueError("Le nombre de pages doit être >= 1")
        return v
```

**Sérialisation JSON**:
```python
import json
from pydantic import BaseModel

def serialize_response(response: ConversionResponse) -> str:
    """Sérialise la réponse en JSON avec encodage UTF-8."""
    return response.model_dump_json(
        indent=2, 
        ensure_ascii=False, 
        by_alias=True
    )

# Exemple d'utilisation:
response = ConversionResponse(
    format="pdf",
    pages=[PageJson(index=0, content="# Titre\n\nContenu")],
    metadata={"total_pages": 1}
)
json_str = serialize_response(response)  # Returns formatted JSON
```

**Gestion des erreurs dans la réponse**:
```python
from fastapi import HTTPException

def handle_conversion_error(error: Exception, request_id: str | None = None) -> dict:
    """Returns a structured error in JSON."""
    return {
        "format": "error",
        "pages": [],
        "content": None,
        "metadata": {},
        "request_id": request_id,
        "success": False,
        "timestamp": datetime.utcnow(),
        "error": str(error) if not isinstance(error, HTTPException) else error.detail
    }
```

**Notes d'implémentation**:
- The `content` field is an alternative to `pages` for simple formats (DOCX, HTML) that return Markdown directly
- Pour les formats complexes (PDF, XLSX), utiliser uniquement le champ `pages` avec la liste des sections
- Les métadonnées doivent être spécifiques au format source et inclure au minimum: `total_pages`, `file_size_bytes`
- L'horodatage doit toujours être en UTC pour la cohérence internationale
- La validation Pydantic garantit l'intégrité des données avant sérialisation

---

### 2.3 Définir le contrat de réponse JSONL

**Objectif**: Spécifier le format JSONL pour les grands documents avec granularité adaptée au chunking. ✅ **COMPLÉTÉ**

**Approche recommandée**: Événements standardisés (cohérents entre tous les convertisseurs)

```jsonl
# Événements standardisés (cohérents entre tous les convertisseurs)
{"type": "start", "index": 0, "metadata": {"source": "pdf_page"}}           # Début document/section
{"type": "chunk", "content": "...", "offset": 1024, "length": 512}          # Fragment chunké
{"type": "end"}                                                            # Fin document/section
```

**Configuration**:
- Paramètre: `CAAS_JSONL_CHUNK_SIZE` (défaut: 1024 caractères)
- Appliqué à tous les convertisseurs textuels (PDF, DOCX, ODT, PPTX, HTML)
- Pour XLSX/ODS (données structurées): une ligne JSONL par ligne de données

**Granularité par type**:
| Type | Unité logique | Granularité | Événements |
|------|---------------|-------------|------------|
| PDF | Page | Chunk textuel (1024 chars) | start, chunk×N, end |
| DOCX/ODT | Section (para, heading) | Chunk textuel (1024 chars) | start, chunk×N, end |
| PPTX | Diapositive | Chunk textuel (1024 chars) | start, chunk×N, end |
| HTML | Élément | Chunk textuel (1024 chars) | start, chunk×N, end |
| XLSX/ODS | Ligne de données | Une ligne par ligne | start, row, end |

**Types d'événements JSONL**:
- `start`: Début d'une section/page/diapositive (index + metadata)
- `chunk`: Fragment de contenu textuel avec offset et length
- `end`: Fin de la section/page/diapositive
- `row` (XLSX/ODS uniquement): Ligne de données complète

**Avantages**:
- Granularité fine pour le streaming et LLM context windows
- Cohérence entre tous les convertisseurs
- Configuration centralisée via `CAAS_JSONL_CHUNK_SIZE`
- Streaming progressif sans attendre tout le document

---

### 2.3.1 Validation du contrat JSONL

**Objectif**: S'assurer que tous les convertisseurs respectent le format JSONL défini. ✅ **COMPLÉTÉ**

**Actions réalisées**:
- [x] Créer un validateur de format JSONL dans `app/utils/jsonl_validator.py`:
  ```python
  import json
  
  def validate_jsonl_line(line: str) -> tuple[bool, dict | None]:
      """Valide une ligne JSONL et retourne (valid, parsed_data)."""
      try:
          data = json.loads(line)
          if "type" not in data or data["type"] not in ["start", "chunk", "end", "row"]:
              return False, None
          return True, data
      except json.JSONDecodeError as e:
          return False, {"error": str(e)}
  ```

- [x] Ajouter validation dans chaque convertisseur JSONL:
  ```python
  def validate_jsonl_output(output: str) -> bool:
      """Valide que tout le output JSONL est correct."""
      for i, line in enumerate(output.split("\n")):
          if not line.strip():
              continue
          valid, data = validate_jsonl_line(line)
          if not valid:
              raise ValueError(f"Ligne {i} invalide: {data}")
      return True
  ```

**Tests de validation**:
- [x] Test: PDF → JSONL (validation du format ligne par ligne)
- [x] Test: DOCX → JSONL
- [x] Test: XLSX → JSONL (vérifier les événements `row`)
- [x] Test: ODT → JSONL

---

### 2.3.2 Performance et optimisation JSONL

**Objectif**: Optimiser la génération de JSONL pour les grands documents. ✅ **COMPLÉTÉ**

**Actions réalisées**:
- [x] Utiliser `io.StringIO` pour éviter les concaténations mémoire:
  ```python
  from io import StringIO
  
  def generate_jsonl_stream(pages, chunk_size=1024):
      output = StringIO()
      for i, page in enumerate(pages):
          # Événement start
          output.write(json.dumps({"type": "start", "index": i}))
          
          # Chunking avec écriture progressive
          content = page["content"]
          for j in range(0, len(content), chunk_size):
              chunk = content[j:j+chunk_size]
              output.write(json.dumps({
                  "type": "chunk", 
                  "content": chunk,
                  "offset": j,
                  "length": len(chunk)
              }))
          
          # Événement end
          output.write(json.dumps({"type": "end"}))
      
      return output.getvalue()
  ```

- [x] Pour les très grands documents (> 10 Mo), utiliser le streaming asynchrone:
  ```python
  async def generate_jsonl_async(pages, chunk_size=1024):
      for i, page in enumerate(pages):
          yield json.dumps({"type": "start", "index": i})
          
          content = page["content"]
          for j in range(0, len(content), chunk_size):
              chunk = content[j:j+chunk_size]
              yield json.dumps({
                  "type": "chunk", 
                  "content": chunk,
                  "offset": j,
                  "length": len(chunk)
              })
          
          yield json.dumps({"type": "end"})
  ```

**Benchmarks à réaliser**:
- [ ] Mesurer la mémoire utilisée pour un document de 100 pages (Markdown vs JSONL)
- [ ] Comparer le temps de génération (batch vs streaming)
- [ ] Tester avec des documents réels (> 5 Mo)

---

## 3. Implémentation des convertisseurs JSON/JSONL

### 3.1 Ajouter les méthodes de conversion JSON aux convertisseurs existants

**Objectif**: Modifier chaque convertisseur pour supporter l'export JSON.

**Actions par fichier**:

#### `app/converters/base.py` - Utilitaires communs ✅ **COMPLÉTÉ**

- [x] **Étape 3.1.1**: Importer `json` module (`import json`)
- [x] **Étape 3.1.2**: Ajouter fonction `_to_json_format(data: dict) -> str`:
  ```python
  def _to_json_format(data: dict) -> str:
      """Convert unstructured data to JSON format."""
      return json.dumps(data, ensure_ascii=False, indent=2)
  ```
- [x] **Étape 3.1.3**: Ajouter fonction `_to_jsonl_format(pages: list[dict]) -> str`:
  ```python
  def _to_jsonl_format(pages: list[dict]) -> str:
      """Convert a list of pages/sections to JSONL format (one JSON object per line)."""
      return "\n".join(json.dumps(page, ensure_ascii=False) for page in pages)
  ```

**Implémentation réalisée**:
- [x] Module `json` importé dans `app/converters/base.py`
- [x] Fonction `_to_json_format()` ajoutée : convertit un dict en JSON avec UTF-8 et indentation
- [x] Fonction `_to_jsonl_format()` ajoutée : convertit une liste de dicts en JSONL (une ligne par objet)

**Utilisation**:
```python
# Exemple d'utilisation dans les convertisseurs:
json_output = _to_json_format({
    "format": "pdf",
    "pages": [{"index": 0, "content": "..."}],
    "metadata": {"total_pages": 1}
})

jsonl_output = _to_jsonl_format([
    {"index": 0, "content": "..."},
    {"index": 1, "content": "..."}
])
```

#### `app/converters/pdf.py` - PDF → JSON/JSONL ✅ **COMPLÉTÉ**

**Approche**: Chunk textuel par blocs de `CAAS_JSONL_CHUNK_SIZE` caractères (défaut: 1024)

- [x] **Étape 3.1.4**: Créer modèles Pydantic dans `app/models/response.py`:
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

- [x] **Étape 3.1.5**: Modifier `_extract_pdf_content()` pour extraire données brutes + Markdown:
  ```python
  def _extract_pdf_data(file_bytes: bytes) -> tuple[list[tuple[int, str, list[str]]], int]:
      # ... extraction existante ...
      return results, total_pages
  ```

- [x] **Étape 3.1.6**: Ajouter méthode `_to_json()` dans `convert_pdf()`:
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

- [x] **Étape 3.1.7**: Ajouter méthode `_to_jsonl()` dans `convert_pdf()` avec chunking textuel:
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
              
              # Chunk the textual content (Markdown) into blocks of CAAS_JSONL_CHUNK_SIZE
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

**Note**: Chunking applies to textual content (Markdown), not metadata. Each chunk respects the configured size for LLM-friendly streaming.
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

#### `app/converters/docx.py` - DOCX → JSON/JSONL ✅ **COMPLÉTÉ**

**Approche**: Chunk textuel par blocs de `CAAS_JSONL_CHUNK_SIZE` caractères (défaut: 1024)

- [x] **Étape 3.1.8**: Créer modèles Pydantic dans `app/models/response.py`:
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

- [x] **Étape 3.1.9**: Modifier `_convert_docx()` pour extraire données brutes + Markdown:
  ```python
  def _extract_docx_data(file_bytes: bytes) -> tuple[list[dict], str]:
      # ... extraction existante ...
      sections = [{"index": i, "content": text} for i, text in enumerate(pages)]
      return sections, markdown_text
  ```

- [x] **Étape 3.1.10**: Ajouter méthode `_to_json()` dans `convert_docx()`:
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

- [x] **Étape 3.1.11**: Ajouter méthode `_to_jsonl()` dans `convert_docx()` avec chunking textuel:
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

#### `app/converters/odt.py` - ODT → JSON/JSONL ✅ **COMPLÉTÉ**

**Approche**: Chunk textuel par blocs de `CAAS_JSONL_CHUNK_SIZE` caractères (défaut: 1024)

- [x] **Étape 3.1.11**: Créer modèles Pydantic dans `app/models/response.py`:
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

- [x] **Étape 3.1.12**: Modifier `_convert_odt()` pour extraire éléments bruts + Markdown:
  ```python
  def _extract_odt_data(file_bytes: bytes) -> tuple[list[dict], str]:
      elements = []
      # ... extraction existante ...
      markdown = "# ..."  # conversion Markdown existante
      return elements, markdown
  ```

- [x] **Étape 3.1.13**: Ajouter méthode `_to_json()` dans `convert_odt()`:
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

- [x] **Étape 3.1.14**: Ajouter méthode `_to_jsonl()` dans `convert_odt()` avec chunking textuel:
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

#### `app/converters/xlsx.py` - XLSX → JSON/JSONL ✅ **COMPLÉTÉ**

**Approche**: Une ligne JSONL par ligne de données (données structurées). Chunking optionnel si une ligne dépasse `CAAS_JSONL_CHUNK_SIZE`.

- [x] **Étape 3.1.14**: Créer modèles Pydantic dans `app/models/response.py`:
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

- [x] **Étape 3.1.15**: Modifier `_convert_xlsx()` pour extraire les feuilles brutes:
  ```python
  def _extract_xlsx_data(file_bytes: bytes) -> list[dict]:
      sheets = []
      for sheet_name, worksheet in workbook.sheetnames.items():
          data = [row for row in worksheet.iter_rows(values_only=True)]
          headers = next(worksheet.row_values(0)) if len(worksheet.row_values(0)) > 0 else None
          sheets.append({"name": sheet_name, "data": data, "headers": headers})
      return sheets
  ```

- [x] **Étape 3.1.16**: Ajouter méthode `_to_json()` dans `convert_xlsx()`:
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

- [x] **Étape 3.1.17**: Ajouter méthode `_to_jsonl()` dans `convert_xlsx()` (une ligne par ligne):
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

#### `app/converters/ods.py` - ODS → JSON/JSONL ✅ **COMPLÉTÉ**

**Approche**: Une ligne JSONL par ligne de données (données structurées). Chunking optionnel si une ligne dépasse `CAAS_JSONL_CHUNK_SIZE`.

- [x] **Étape 3.1.17**: Créer modèles Pydantic dans `app/models/response.py`:
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

- [x] **Étape 3.1.18**: Modifier `_convert_ods()` pour extraire les cellules brutes:
  ```python
  def _extract_ods_data(file_bytes: bytes) -> list[dict]:
      cells = []
      # ... extraction existante ...
      return cells
  ```

- [x] **Étape 3.1.19**: Ajouter méthode `_to_json()` dans `convert_ods()`:
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

- [x] **Étape 3.1.20**: Ajouter méthode `_to_jsonl()` dans `convert_ods()` (une ligne par ligne):
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
- [x] **Étape 3.1.18**: Modifier `_convert_ods()` pour extraire les cellules brutes:
  ```python
  def _extract_ods_data(file_bytes: bytes) -> list[dict]:
      cells = []
      # ... extraction existante ...
      return cells
  ```
- [x] **Étape 3.1.19**: Ajouter méthodes `_to_json()` et `_to_jsonl()` dans `convert_ods()`:
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

#### `app/converters/pptx.py` - PPTX → JSON/JSONL ✅ **COMPLÉTÉ**

**Approche**: Chunk textuel par diapositive (comme PDF/DOCX). Chaque diapositive est chunkée en blocs de `CAAS_JSONL_CHUNK_SIZE`.

- [x] **Étape 3.1.20**: Créer modèles Pydantic dans `app/models/response.py`:
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

- [x] **Étape 3.1.21**: Modifier `_convert_pptx()` pour extraire les diapositives brutes:
  ```python
  def _extract_pptx_data(file_bytes: bytes) -> list[dict]:
      slides = []
      # ... extraction existante ...
      return slides
  ```

- [x] **Étape 3.1.22**: Ajouter méthode `_to_json()` dans `convert_pptx()`:
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

- [x] **Étape 3.1.23**: Ajouter méthode `_to_jsonl()` dans `convert_pptx()` (chunk textuel):
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
- [x] **Étape 3.1.21**: Modifier `_convert_pptx()` pour extraire les diapositives brutes:
  ```python
  def _extract_pptx_data(file_bytes: bytes) -> list[dict]:
      slides = []
      # ... extraction existante ...
      return slides
  ```
- [x] **Étape 3.1.22**: Ajouter méthodes `_to_json()` et `_to_jsonl()` dans `convert_pptx()`:
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

#### `app/converters/odp.py` - ODP → JSON/JSONL ✅ **COMPLÉTÉ**

- [x] **Étape 3.1.23**: Créer modèle Pydantic `OdpSlideJson`:
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
- [x] **Étape 3.1.24**: Modifier `_convert_odp()` pour extraire les slides brutes:
  ```python
  def _extract_odp_data(file_bytes: bytes) -> list[dict]:
      slides = []
      # ... extraction existante ...
      return slides
  ```
- [x] **Étape 3.1.25**: Ajouter méthodes `_to_json()` et `_to_jsonl()` dans `convert_odp()`:
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

#### `app/converters/html.py` - HTML → JSON/JSONL ✅ **COMPLÉTÉ**

**Approche**: Chunk textuel par élément HTML (comme PDF/PPTX/ODP). Chaque élément est chunké en blocs de `CAAS_JSONL_CHUNK_SIZE`.

- [x] **Étape 3.1.26**: Créer modèles Pydantic dans `app/models/response.py`:
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

- [x] **Étape 3.1.27**: Modifier `_convert_html()` pour extraire les éléments bruts:
  ```python
  def _extract_html_data(file_bytes: bytes) -> list[dict]:
      elements = []
      # ... extraction existante avec BeautifulSoup ...
      return elements
  ```

- [x] **Étape 3.1.28**: Ajouter méthode `_to_json()` dans `convert_html()`:
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

- [x] **Étape 3.1.29**: Ajouter méthode `_to_jsonl()` dans `convert_html()` (chunk textuel):
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

### 3.2 Modifier l'orchestrateur de conversion ✅ **COMPLÉTÉ**

**Objectif**: Mettre à jour `app/converter.py` pour supporter les nouveaux formats. ✅ **RÉALISÉ**

**Actions réalisées**:
- [x] Importer tous les modules des convertisseurs JSON/JSONL dans `app/converter.py`:
  ```python
  from app.converters.docx import (
      convert_docx_to_md,
      convert_docx_to_json,
      convert_docx_to_jsonl,
  )
  # ... mêmes imports pour html, odp, ods, odt, pdf, pptx, xlsx
  ```

- [x] Créer les dictionnaires de routage dans `_convert_worker()`:
  ```python
  converters = {
      "pdf": convert_pdf_to_md,
      "docx": convert_docx_to_md,
      # ... autres formats markdown
  }

  json_converters = {
      "pdf": convert_pdf_to_json,
      "docx": convert_docx_to_json,
      # ... autres formats JSON
  }

  jsonl_converters = {
      "pdf": convert_pdf_to_jsonl,
      "docx": convert_docx_to_jsonl,
      # ... autres formats JSONL
  }
  ```

- [x] Implémenter la logique de routage selon le format:
  ```python
  if output_format == "json":
      result = await asyncio.to_thread(json_converter, file_bytes)
  elif output_format == "jsonl":
      result = await asyncio.to_thread(jsonl_converter, file_bytes)
  else:  # markdown (default)
      result = await asyncio.to_thread(converter, file_bytes)

  return {
      "success": True,
      "markdown": result if output_format == "markdown" else None,
      "json": result if output_format == "json" else None,
      "jsonl": result if output_format == "jsonl" else None,
      "format": ext,
      "size_bytes": len(file_bytes),
  }
  ```

**Fichier implémenté**: [`app/converter.py`](d:\Projets\caas\app\converter.py)

**Détails de l'implémentation**:
- Le worker `_convert_worker()` supporte les trois formats: `markdown`, `json`, `jsonl`
- Chaque convertisseur a ses propres fonctions asynchrones synchronisées via `asyncio.to_thread()`:
  - `convert_*_to_md()` pour le format Markdown (défaut)
  - `convert_*_to_json()` pour le format JSON structuré
  - `convert_*_to_jsonl()` pour le format JSONL (streaming)
- Le résultat est retourné dans un dict avec les clés `markdown`, `json`, `jsonl` selon le format demandé

**Validation**:
- [x] Tous les convertisseurs ont leurs fonctions JSON/JSONL implémentées
- [x] L'orchestrateur route correctement vers les bonnes fonctions selon le paramètre `output_format`
- [x] Le résultat est structuré de manière cohérente pour tous les formats

---

### 3.3 Modifier le streaming pour JSON/JSONL ✅ **COMPLÉTÉ**

**Objectif**: Adapter `app/streaming.py` pour supporter le streaming JSON et JSONL avec granularité adaptée au chunking.

**Actions réalisées**:
- [x] Importer les fonctions de conversion JSON/JSONL dans `app/streaming.py`
- [x] Créer les générateurs async pour chaque format (PDF, DOCX, ODT, HTML, XLSX, PPTX, ODS, ODP)
- [x] Implémenter le chunking textuel pour les formats textuels avec `CAAS_JSONL_CHUNK_SIZE`
- [x] Ajouter événements de début/fin pour chaque unité logique (page, section, diapositive)

**Fichier implémenté**: [`app/streaming.py`](d:\Projets\caas\app\streaming.py)

---

#### 3.3.1 Streaming JSON structuré ✅ **COMPLÉTÉ**

**Objectif**: Envoyer des événements JSON complets par page/section/diapositive.

**Approche**: Chaque événement contient un objet JSON complet avec la structure définie dans `app/models/response.py`.

**Implémentation pour PDF**:
```python
async def _convert_pdf_stream_json(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream PDF → JSON conversion, yielding one page per event.
    
    Each page is sent as a complete JSON object with index, content and URLs.
    """
    # Extraction des données brutes (pages + metadata)
    pages_data = await asyncio.to_thread(_extract_pdf_content_raw, file_bytes)
    
    start_event = json.dumps({
        "format": "pdf", 
        "status": "started", 
        "total_pages": len(pages_data),
        "size_bytes": len(file_bytes)
    })
    yield _sse_event(start_event)
    
    for idx, (page_idx, content, urls) in enumerate(pages_data):
        page_json = {
            "type": "page", 
            "index": page_idx, 
            "content": content, 
            "urls": urls
        }
        yield _sse_event(json.dumps(page_json, ensure_ascii=False))
    
    end_event = json.dumps({"status": "complete"})
    yield _sse_event(end_event)
```

**Implémentation pour DOCX**:
```python
async def _convert_docx_stream_json(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream DOCX → JSON conversion, yielding one section per event.
    
    Each section is sent as a complete JSON object with index and content.
    """
    # Extraction des sections (paragraphes + tables)
    sections_data = await asyncio.to_thread(_extract_docx_sections_raw, file_bytes)
    
    start_event = json.dumps({
        "format": "docx", 
        "status": "started", 
        "total_sections": len(sections_data),
        "size_bytes": len(file_bytes)
    })
    yield _sse_event(start_event)
    
    for idx, section in enumerate(sections_data):
        section_json = {
            "type": "section", 
            "index": idx, 
            "content": section["content"], 
            "tables": section.get("tables", [])
        }
        yield _sse_event(json.dumps(section_json, ensure_ascii=False))
    
    end_event = json.dumps({"status": "complete"})
    yield _sse_event(end_event)
```

**Implémentation pour XLSX (données structurées)**:
```python
async def _convert_xlsx_stream_json(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream XLSX → JSON conversion, yielding one sheet per event.
    
    Each sheet is sent as a complete JSON object with name and data rows.
    No chunking for structured data - one row per line in JSONL mode.
    """
    sheets_data = await asyncio.to_thread(_extract_xlsx_sheets_raw, file_bytes)
    
    start_event = json.dumps({
        "format": "xlsx", 
        "status": "started", 
        "total_sheets": len(sheets_data),
        "size_bytes": len(file_bytes)
    })
    yield _sse_event(start_event)
    
    for idx, sheet in enumerate(sheets_data):
        sheet_json = {
            "type": "sheet", 
            "index": idx, 
            "name": sheet["name"], 
            "data": sheet["data"], 
            "headers": sheet.get("headers")
        }
        yield _sse_event(json.dumps(sheet_json, ensure_ascii=False))
    
    end_event = json.dumps({"status": "complete"})
    yield _sse_event(end_event)
```

---

#### 3.3.2 Streaming JSONL avec chunking ✅ **COMPLÉTÉ**

**Objectif**: Envoyer des événements JSONL granulaires pour le streaming progressif et LLM-friendly.

**Approche**: Chunk textuel par blocs de `CAAS_JSONL_CHUNK_SIZE` caractères (défaut: 1024). Événements standardisés: `start`, `chunk`, `end`.

**Implémentation pour PDF (formats textuels)**:
```python
async def _convert_pdf_stream_jsonl(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream PDF → JSONL conversion with chunking.
    
    Each page is split into chunks of CAAS_JSONL_CHUNK_SIZE characters.
    Events: start (page), chunk×N, end (page).
    """
    pages_data = await asyncio.to_thread(_extract_pdf_content_raw, file_bytes)
    chunk_size = settings.jsonl_chunk_size or 1024
    
    for page_idx, content, urls in pages_data:
        # Événement start de la page
        yield _sse_event(json.dumps({
            "type": "start", 
            "index": page_idx, 
            "metadata": {"source": f"pdf_page_{page_idx}", "urls_count": len(urls)}
        }, ensure_ascii=False))
        
        # Chunker le contenu textuel (Markdown) par blocs
        for i in range(0, len(content), chunk_size):
            chunk_content = content[i:i+chunk_size]
            yield _sse_event(json.dumps({
                "type": "chunk", 
                "content": chunk_content,
                "offset": i,
                "length": len(chunk_content)
            }, ensure_ascii=False))
        
        # Événement end de la page
        yield _sse_event(json.dumps({
            "type": "end", 
            "index": page_idx, 
            "urls": urls
        }, ensure_ascii=False))
    
    # Événement final de fin de document
    yield _sse_event(json.dumps({"type": "document_end"}))
```

**Implémentation pour DOCX (formats textuels)**:
```python
async def _convert_docx_stream_jsonl(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream DOCX → JSONL conversion with chunking.
    
    Each section is split into chunks of CAAS_JSONL_CHUNK_SIZE characters.
    Events: start (section), chunk×N, end (section).
    """
    sections_data = await asyncio.to_thread(_extract_docx_sections_raw, file_bytes)
    chunk_size = settings.jsonl_chunk_size or 1024
    
    for idx, section in enumerate(sections_data):
        content = section["content"]
        
        # Événement start de la section
        yield _sse_event(json.dumps({
            "type": "start", 
            "index": idx, 
            "metadata": {"source": f"docx_section_{idx}", "tables_count": len(section.get("tables", []))}
        }, ensure_ascii=False))
        
        # Chunker le contenu textuel par blocs
        for i in range(0, len(content), chunk_size):
            chunk_content = content[i:i+chunk_size]
            yield _sse_event(json.dumps({
                "type": "chunk", 
                "content": chunk_content,
                "offset": i,
                "length": len(chunk_content)
            }, ensure_ascii=False))
        
        # Événement end de la section
        yield _sse_event(json.dumps({
            "type": "end", 
            "index": idx
        }, ensure_ascii=False))
    
    # Événement final de fin de document
    yield _sse_event(json.dumps({"type": "document_end"}))
```

**Implémentation pour XLSX (données structurées - pas de chunking)**:
```python
async def _convert_xlsx_stream_jsonl(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream XLSX → JSONL conversion for structured data.
    
    One JSON line per row (no chunking). Events: start (sheet), row×N, end (sheet).
    Chunking only if a single row exceeds CAAS_JSONL_CHUNK_SIZE.
    """
    sheets_data = await asyncio.to_thread(_extract_xlsx_sheets_raw, file_bytes)
    chunk_size = settings.jsonl_chunk_size or 1024
    
    for idx, sheet in enumerate(sheets_data):
        # Événement start de la feuille
        yield _sse_event(json.dumps({
            "type": "start", 
            "index": idx, 
            "metadata": {"source": f"xlsx_sheet_{sheet['name']}", "rows_count": len(sheet["data"])}
        }, ensure_ascii=False))
        
        for row_idx, row in enumerate(sheet["data"]):
            # Une ligne JSONL par ligne (données structurées)
            line_content = json.dumps(row, ensure_ascii=False)
            
            # Chunking optionnel si la ligne dépasse la taille configurée
            if len(line_content) > chunk_size:
                for i in range(0, len(line_content), chunk_size):
                    yield _sse_event(json.dumps({
                        "type": "chunk", 
                        "content": line_content[i:i+chunk_size],
                        "offset": i,
                        "length": len(line_content[i:i+chunk_size])
                    }, ensure_ascii=False))
            else:
                # Événement row direct pour les lignes normales
                yield _sse_event(json.dumps({
                    "type": "row", 
                    "index": row_idx, 
                    "data": row
                }, ensure_ascii=False))
        
        # Événement end de la feuille
        yield _sse_event(json.dumps({"type": "end", "index": idx}))
    
    # Événement final de fin de document
    yield _sse_event(json.dumps({"type": "document_end"}))
```

**Implémentation pour PPTX (formats textuels)**:
```python
async def _convert_pptx_stream_jsonl(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream PPTX → JSONL conversion with chunking.
    
    Each slide is split into chunks of CAAS_JSONL_CHUNK_SIZE characters.
    Events: start (slide), chunk×N, end (slide).
    """
    slides_data = await asyncio.to_thread(_extract_pptx_slides_raw, file_bytes)
    chunk_size = settings.jsonl_chunk_size or 1024
    
    for idx, slide in enumerate(slides_data):
        # Concaténer le contenu textuel de la diapositive
        content_text = " ".join(slide.get("content", []))
        
        # Événement start de la diapositive
        yield _sse_event(json.dumps({
            "type": "start", 
            "index": idx, 
            "metadata": {"source": f"pptx_slide_{idx}", "title": slide.get("title")}
        }, ensure_ascii=False))
        
        # Chunker le contenu textuel de la diapositive par blocs
        for i in range(0, len(content_text), chunk_size):
            chunk_content = content_text[i:i+chunk_size]
            yield _sse_event(json.dumps({
                "type": "chunk", 
                "content": chunk_content,
                "offset": i,
                "length": len(chunk_content)
            }, ensure_ascii=False))
        
        # Événement end de la diapositive
        yield _sse_event(json.dumps({
            "type": "end", 
            "index": idx
        }, ensure_ascii=False))
    
    # Événement final de fin de document
    yield _sse_event(json.dumps({"type": "document_end"}))
```

**Implémentation pour HTML (formats textuels)**:
```python
async def _convert_html_stream_jsonl(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream HTML → JSONL conversion with chunking.
    
    Each element is split into chunks of CAAS_JSONL_CHUNK_SIZE characters.
    Events: start (element), chunk×N, end (element).
    """
    elements_data = await asyncio.to_thread(_extract_html_elements_raw, file_bytes)
    chunk_size = settings.jsonl_chunk_size or 1024
    
    for idx, element in enumerate(elements_data):
        content_text = element.get("content", "")
        
        # Événement start de l'élément HTML
        yield _sse_event(json.dumps({
            "type": "start", 
            "index": idx, 
            "metadata": {"tag": element.get("tag", ""), "attributes": str(element.get("attributes", {}))}
        }, ensure_ascii=False))
        
        # Chunker le contenu textuel de l'élément HTML par blocs
        for i in range(0, len(content_text), chunk_size):
            chunk_content = content_text[i:i+chunk_size]
            yield _sse_event(json.dumps({
                "type": "chunk", 
                "content": chunk_content,
                "offset": i,
                "length": len(chunk_content)
            }, ensure_ascii=False))
        
        # Événement end de l'élément HTML
        yield _sse_event(json.dumps({
            "type": "end", 
            "index": idx
        }, ensure_ascii=False))
    
    # Événement final de fin de document
    yield _sse_event(json.dumps({"type": "document_end"}))
```

**Implémentation pour ODT (formats textuels)**:
```python
async def _convert_odt_stream_jsonl(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream ODT → JSONL conversion with chunking.
    
    Each element is split into chunks of CAAS_JSONL_CHUNK_SIZE characters.
    Events: start (element), chunk×N, end (element).
    """
    elements_data = await asyncio.to_thread(_extract_odt_elements_raw, file_bytes)
    chunk_size = settings.jsonl_chunk_size or 1024
    
    for idx, element in enumerate(elements_data):
        content_text = element["content"]
        
        # Événement start de l'élément ODT
        yield _sse_event(json.dumps({
            "type": "start", 
            "index": idx, 
            "metadata": {"type": element["type"], "level": element.get("level", 0)}
        }, ensure_ascii=False))
        
        # Chunker le contenu textuel de l'élément ODT par blocs
        for i in range(0, len(content_text), chunk_size):
            chunk_content = content_text[i:i+chunk_size]
            yield _sse_event(json.dumps({
                "type": "chunk", 
                "content": chunk_content,
                "offset": i,
                "length": len(chunk_content)
            }, ensure_ascii=False))
        
        # Événement end de l'élément ODT
        yield _sse_event(json.dumps({
            "type": "end", 
            "index": idx
        }, ensure_ascii=False))
    
    # Événement final de fin de document
    yield _sse_event(json.dumps({"type": "document_end"}))
```

**Implémentation pour ODS (données structurées - pas de chunking)**:
```python
async def _convert_ods_stream_jsonl(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream ODS → JSONL conversion for structured data.
    
    One JSON line per row (no chunking). Events: start (sheet), row×N, end (sheet).
    Chunking only if a single row exceeds CAAS_JSONL_CHUNK_SIZE.
    """
    sheets_data = await asyncio.to_thread(_extract_ods_sheets_raw, file_bytes)
    chunk_size = settings.jsonl_chunk_size or 1024
    
    for idx, sheet in enumerate(sheets_data):
        # Événement start de la feuille
        yield _sse_event(json.dumps({
            "type": "start", 
            "index": idx, 
            "metadata": {"source": f"ods_sheet_{sheet['name']}", "rows_count": len(sheet["data"])}
        }, ensure_ascii=False))
        
        for row_idx, row in enumerate(sheet["data"]):
            # Une ligne JSONL par ligne (données structurées)
            line_content = json.dumps(row, ensure_ascii=False)
            
            # Chunking optionnel si la ligne dépasse la taille configurée
            if len(line_content) > chunk_size:
                for i in range(0, len(line_content), chunk_size):
                    yield _sse_event(json.dumps({
                        "type": "chunk", 
                        "content": line_content[i:i+chunk_size],
                        "offset": i,
                        "length": len(line_content[i:i+chunk_size])
                    }, ensure_ascii=False))
            else:
                # Événement row direct pour les lignes normales
                yield _sse_event(json.dumps({
                    "type": "row", 
                    "index": row_idx, 
                    "data": row
                }, ensure_ascii=False))
        
        # Événement end de la feuille
        yield _sse_event(json.dumps({"type": "end", "index": idx}))
    
    # Événement final de fin de document
    yield _sse_event(json.dumps({"type": "document_end"}))
```

**Implémentation pour ODP (formats textuels)**:
```python
async def _convert_odp_stream_jsonl(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Stream ODP → JSONL conversion with chunking.
    
    Each slide is split into chunks of CAAS_JSONL_CHUNK_SIZE characters.
    Events: start (slide), chunk×N, end (slide).
    """
    slides_data = await asyncio.to_thread(_extract_odp_slides_raw, file_bytes)
    chunk_size = settings.jsonl_chunk_size or 1024
    
    for idx, slide in enumerate(slides_data):
        # Concaténer le contenu textuel de la diapositive
        content_text = " ".join(slide.get("content", []))
        
        # Événement start de la diapositive
        yield _sse_event(json.dumps({
            "type": "start", 
            "index": idx, 
            "metadata": {"source": f"odp_slide_{idx}", "title": slide.get("title")}
        }, ensure_ascii=False))
        
        # Chunker le contenu textuel de la diapositive par blocs
        for i in range(0, len(content_text), chunk_size):
            chunk_content = content_text[i:i+chunk_size]
            yield _sse_event(json.dumps({
                "type": "chunk", 
                "content": chunk_content,
                "offset": i,
                "length": len(chunk_content)
            }, ensure_ascii=False))
        
        # Événement end de la diapositive
        yield _sse_event(json.dumps({
            "type": "end", 
            "index": idx
        }, ensure_ascii=False))
    
    # Événement final de fin de document
    yield _sse_event(json.dumps({"type": "document_end"}))
```

**Résumé des stratégies de chunking**:
- **Formats textuels** (PDF, DOCX, ODT, HTML, PPTX, ODP): Chunking activé par défaut avec `CAAS_JSONL_CHUNK_SIZE` (1024 chars) pour optimiser le contexte LLM
- **Formats structurés** (XLSX, ODS): Pas de chunking artificiel - une ligne JSONL par ligne de données, chunking optionnel uniquement si une ligne dépasse la taille configurée

---

#### 3.3.3 Wrapper functions et orchestration ✅ **COMPLÉTÉ**

**Objectif**: Créer des fonctions wrapper dans `app/streaming.py` pour chaque format avec les deux modes (JSON structuré et JSONL chunké).

**Implémentation complète dans app/streaming.py**:
```python
from .converter import (
    _extract_pdf_content_raw, 
    _extract_docx_sections_raw, 
    _extract_odt_elements_raw,
    _extract_html_elements_raw,
    _extract_xlsx_sheets_raw,
    _extract_pptx_slides_raw,
    _extract_ods_sheets_raw,
    _extract_odp_slides_raw
)

async def convert_pdf_stream_json(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Wrapper pour PDF → JSON streaming."""
    async for chunk in _convert_pdf_stream_json(file_bytes):
        yield chunk

async def convert_pdf_stream_jsonl(file_bytes: bytes) -> AsyncGenerator[str, None]:
    """Wrapper pour PDF → JSONL streaming avec chunking."""
    async for chunk in _convert_pdf_stream_jsonl(file_bytes):
        yield chunk

# ... mêmes wrappers pour tous les formats (DOCX, ODT, HTML, XLSX, PPTX, ODS, ODP)
```

**Configuration des paramètres**:
- Paramètre `format` dans les routes: `"markdown" | "json" | "jsonl"`
- Paramètre `streaming` pour activer le mode SSE (défaut: `False`)
- Paramètre `chunk_size` optionnel pour surcharger `CAAS_JSONL_CHUNK_SIZE`

---

## 3.4 Mettre à jour les routes ✅ **COMPLÉTÉ**

**Objectif**: Modifier `app/routes/convert.py` pour accepter le paramètre format.

**Actions réalisées**:
- [x] Ajouter validation du paramètre format avec `Literal["markdown", "json", "jsonl"]`
- [x] Modifier l'appel au convertisseur avec le paramètre format
- [x] Gérer les réponses HTTP selon le format (JSON, Markdown, JSONL)

**Implémentation dans [`app/routes/convert.py`](d:\Projets\caas\app\routes\convert.py)**:

```python
from typing import Literal
from fastapi import Query, Response
from app.converter import convert_file

async def convert_endpoint(
    file: UploadFile, 
    format: str = "markdown",  # markdown | json | jsonl
):
    """Endpoint de conversion avec support JSON/JSONL."""
    
    # Validation du paramètre format
    if format not in ["markdown", "json", "jsonl"]:
        raise HTTPException(
            status_code=400, 
            detail="Format invalide. Doit être 'markdown', 'json' ou 'jsonl'."
        )
    
    # Conversion selon le format demandé
    file_bytes = await file.read()
    ext = file.filename.split(".")[-1].lower() if file.filename else "pdf"
    
    result = await convert_file(file_bytes, ext, format=format)
    
    # Gestion des réponses HTTP selon le format
    if format == "jsonl":
        # JSONL: retourne text/plain avec une ligne JSON par événement
        return Response(
            content=result, 
            media_type="text/plain; charset=utf-8"
        )
    elif format == "json":
        # JSON structuré: retourne application/json
        from app.models.response import ConversionResponse
        response = ConversionResponse(format=ext, pages=result.get("pages", []))
        return JSONResponse(
            content=response.model_dump(), 
            media_type="application/json"
        )
    else:  # markdown (défaut)
        # Markdown brut: retourne text/plain
        return Response(
            content=result, 
            media_type="text/markdown; charset=utf-8"
        )
```

**Paramètres d'endpoint**:
| Paramètre | Type | Valeurs possibles | Défaut | Description |
|-----------|------|-------------------|--------|-------------|
| `format` | query string | `"markdown"`, `"json"`, `"jsonl"` | `"markdown"` | Format de sortie souhaité |

**Comportement par format**:
- **Markdown (défaut)**: Retourne une chaîne Markdown brute (`text/markdown`)
- **JSON**: Retourne un objet JSON structuré avec métadonnées et contenu paginé (`application/json`)
- **JSONL**: Retourne du texte brut avec une ligne JSON par événement pour le streaming (`text/plain; charset=utf-8`)

**Exemples d'utilisation**:
```bash
# Export en Markdown (défaut)
curl -X POST "http://localhost:8000/convert" \
     -F "file=@document.pdf"

# Export en JSON structuré
curl -X POST "http://localhost:8000/convert?format=json" \
     -F "file=@document.pdf"

# Export en JSONL (streaming)
curl -X POST "http://localhost:8000/convert?format=jsonl" \
     -F "file=@document.pdf"
```

**Validation du paramètre format**:
```python
from typing import Literal

def convert_endpoint(file, format: str = "markdown"):
    if format not in ["markdown", "json", "jsonl"]:
        raise HTTPException(
            status_code=400, 
            detail="Format invalide. Doit être 'markdown', 'json' ou 'jsonl'."
        )
```

**Notes d'implémentation**:
- Le paramètre `format` est optionnel et par défaut retourne Markdown (comportement existant)
- Pour JSONL en streaming, chaque événement SSE correspond à une ligne JSON complète
- Pour JSON non-streaming, la réponse contient tout le document dans un objet JSON unique
- La validation Pydantic garantit l'intégrité des données avant sérialisation

---

### 3.5 Mettre à jour les routes batch ✅ **COMPLÉTÉ**

**Objectif**: Modifier `app/routes/batch.py` pour accepter le paramètre format avec validation et gestion des réponses HTTP selon le format.

**Actions réalisées**:
- [x] Ajouter import de `Response` dans `fastapi.responses`
- [x] Ajouter paramètre `format: str | None = Query(default=None, alias="format")` à l'endpoint `/convert/batch`
- [x] Implémenter validation du paramètre format avec valeur par défaut "markdown"
- [x] Gérer les réponses HTTP selon le format (JSON, Markdown, JSONL)

**Implémentation dans [`app/routes/batch.py`](d:\Projets\caas\app\routes\batch.py)**:

```python
from fastapi.responses import Response  # Ajout

@app.post("/convert/batch", response_model=dict[str, Any])
async def convert_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    format: str | None = Query(default=None, alias="format"),  # Nouveau paramètre
    async_mode: str | None = Query(default=None, alias="async"),
):
    """
    Convert multiple documents to Markdown/JSON/JSONL in a single request.
    
    **Format options**:
    - `format=markdown` (default): returns Markdown text separated by newlines
    - `format=json`: returns structured JSON with per-file results
    - `format=jsonl`: returns Server-Sent Events (SSE) with one JSON line per file
    """
    
    # --- 0. Validation du paramètre format ---
    if format is None:
        format = "markdown"
    
    valid_formats = ["markdown", "json", "jsonl"]
    if format not in valid_formats:
        logger.warning(
            "[%s] Rejected batch from %s: invalid format '%s'",
            batch_id, client_ip, format,
        )
        error(400, "INVALID_FORMAT")
    
    # ... reste du code de validation et conversion ...
```

**Gestion des réponses HTTP selon le format**:

```python
# --- 8. Gestion des réponses HTTP selon le format ---
if format == "jsonl":
    # Streaming JSONL: une ligne JSON par fichier
    content = "\n".join(
        f'{{"index": {i}, "filename": "{r["filename"]}", '
        f'"success": {str(r["success"]).lower()}, '
        f'"result": {r.get("markdown") or r.get("error")}}}'
        for i, r in enumerate(results)
    )
    return Response(content=content, media_type="text/plain; charset=utf-8")

elif format == "json":
    # JSON structuré avec toutes les métadonnées
    from app.models.response import BatchConversionResponse
    
    response_data = {
        "batch_id": batch_id,
        "total_files": len(files),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
    
    pydantic_response = BatchConversionResponse(**response_data)
    return JSONResponse(
        content=pydantic_response.model_dump(), 
        media_type="application/json"
    )

else:  # markdown (défaut)
    markdown_content = "\n\n".join(r.get("markdown", "") for r in results if r.get("success"))
    return Response(content=markdown_content, media_type="text/markdown; charset=utf-8")
```

**Paramètres d'endpoint**:
| Paramètre | Type | Valeurs possibles | Défaut | Description |
|-----------|------|-------------------|--------|-------------|
| `format` | query string | `"markdown"`, `"json"`, `"jsonl"` | `"markdown"` | Format de sortie souhaité |

**Comportement par format**:
- **Markdown (défaut)**: Retourne une chaîne Markdown brute avec les documents séparés par `\n\n` (`text/markdown`)
- **JSON**: Retourne un objet JSON structuré avec métadonnées et contenu paginé pour chaque fichier (`application/json`)
- **JSONL**: Retourne du texte brut avec une ligne JSON par événement pour le streaming (`text/plain; charset=utf-8`)

**Exemples d'utilisation**:
```bash
# Export batch en Markdown (défaut)
curl -X POST "http://localhost:8000/convert/batch" \
     -F "file=@document1.pdf" \
     -F "file=@document2.docx"

# Export batch en JSON structuré
curl -X POST "http://localhost:8000/convert/batch?format=json" \
     -F "file=@document1.pdf" \
     -F "file=@document2.docx"

# Export batch en JSONL (streaming)
curl -X POST "http://localhost:8000/convert/batch?format=jsonl" \
     -F "file=@document1.pdf" \
     -F "file=@document2.docx"
```

**Validation du paramètre format**:
- Le paramètre `format` est optionnel et par défaut retourne Markdown (comportement existant)
- Si le format n'est pas valide, une erreur HTTP 400 est retournée avec le code d'erreur "INVALID_FORMAT"
- La validation Pydantic garantit l'intégrité des données avant sérialisation

**Notes d'implémentation**:
- Le paramètre `format` est optionnel et par défaut retourne Markdown (comportement existant)
- Pour JSONL en streaming, chaque événement SSE correspond à une ligne JSON complète
- Pour JSON non-streaming, la réponse contient tout le document dans un objet JSON unique avec métadonnées batch
- La validation Pydantic garantit l'intégrité des données avant sérialisation

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

## 4. Tests unitaires et d'intégration

### 4.1 Créer des fixtures de test ✅

**Objectif**: Préparer les données de test pour les nouveaux formats.

**Actions**:
- [x] Dans `tests/conftest.py`: ajouter fixtures pour JSON/JSONL
- [x] Fixture `sample_pdf_bytes` (déjà existant)
- [x] Créer fixture `expected_json_output` pour chaque type de fichier (PDF, DOCX, ODT, XLSX, PPTX, HTML, ODS, ODP)
- [x] Créer fixture `expected_jsonl_output` pour chaque type de fichier avec structure d'événements complète

**Détails**:
- Ajout de 16 fixtures dans `tests/conftest.py`:
  - 8 fixtures JSON (`expected_json_output_*`) pour chaque format supporté
  - 8 fixtures JSONL (`expected_jsonl_output_*`) avec événements start/chunk/end
  - Structures adaptées aux formats tabulaires (XLSX/ODS) et présentations (PPTX/ODP)

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
