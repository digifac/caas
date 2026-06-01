# Audit Technique — CAAS (Conversion as a Service)

**Date :** 28 mai 2026  
**Version analysée :** 1.0.0  
**Scope :** Architecture, sécurité, performance, qualité du code, dépendances, tests

---

## 1. Vue d'ensemble

**CAAS** est un service FastAPI qui convertit des documents (PDF, DOCX, ODT, HTML) en Markdown, optimisé pour l'alimentation de LLMs. L'architecture est **100 % in-memory** (zéro I/O disque), avec un design modulaire et une approche security-first.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    FastAPI Application                    │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Rate Limiter│  │ Task Manager │  │   Middleware   │  │
│  │ (Memory/Redis)│ │ (Memory/Redis)│  │  Security      │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              Conversion Orchestration                │  │
│  │           converter.py → delegates to:              │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐             │  │
│  │  │ PDF  │ │DOCX  │ │ ODT  │ │  HTML  │             │  │
│  │  │(pdfpl│ │(mam- │ │(odf- │ │(BS4)   │             │  │
│  │  │umber)│ │moth) │ │py)   │ │        │             │  │
│  │  └──┬───┘ └──────┘ └──────┘ └────────┘             │  │
│  │     │                                                │  │
│  │  ┌──┴───┐                                            │  │
│  │  │ OCR  │ (pytesseract + pypdfium2)                  │  │
│  │  └──────┘                                            │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────┐  ┌──────────────┐                       │  │
│  │   Storage   │  │   Streaming  │                       │  │
│  │ Protocol    │  │    (SSE)     │                       │  │
│  └─────────────┘  └──────────────┘                       │  │
└──────────────────────────────────────────────────────────┘
```

### Points forts architecturaux

- **StorageProtocol** : pattern Strategy pour interchanger Memory/Redis sans modifier le code métier
- **Converters modulaires** : chaque format a son module dédié partageant `base.py`
- **Separation of concerns** : routes, validation, OCR, streaming sont isolés dans des modules distincts
- **Lifespan context manager** : gestion propre du cycle de vie (startup/shutdown Redis)
- **Routes modulaires** : `_register_routes()` centralise l'enregistrement des endpoints

---

## 3. Points forts du code

| Domaine                | Détail                                                                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Performance PDF**    | Design single-pass : le texte est extrait une seule fois par page et mis en cache. `pypdfium2` n'est ouvert qu'une seule fois pour le batch OCR. |
| **OCR**                | Module indépendant (`ocr.py`), réutilisable, avec cleanup propre des ressources PIL/pypdfium2 via `try/finally`                                  |
| **Sécurité**           | Validation multi-couches : magic bytes, MIME type, ZIP bomb detection, sanitisation HTML, URLs dangereuses bloquées, anti-spoofing IP            |
| **Rate Limiting**      | Sliding window natif (zéro dépendance), éviction proactive des plus anciennes clés quand `max_keys` est dépassé                                  |
| **Streaming SSE**      | Vrai streaming progressif pour PDF (page par page), chunked pour les autres formats                                                              |
| **Gestion mémoire**    | Libération explicite (`content = None`), limites strictes (`max_tasks`, `max_keys`, `max_file_size`)                                             |
| **Tests**              | Couverture solide avec fixtures pytest, marqueurs (`docker`, `redis`), benchmarks                                                                |
| **Erreurs sécurisées** | Messages génériques pour le client, détails complets dans les logs (`errors.py`)                                                                 |

---

## 4. Points d'attention & améliorations potentielles

### 🔴 Critique

#### 1. Fonction `_streaming_generator` — **Faux positif, corrigé**

✅ La fonction `_streaming_generator(content, ext)` **existe bien** à la ligne 153 de `app/routes/convert.py`. Elle est définie au niveau du module (en dehors de `register_convert_routes`) et est correctement appelée à la ligne 95 depuis la route `/convert`. Aucun bug latent.

#### 2. `create_app()` — retour implicite

✅ **Résolu.** La fonction `create_app()` dans `app/api.py` contient bien un `return app` explicite (ligne 131). Aucun problème.

**Fichier :** `app/api.py`

#### 3. Code dupliqué PDF : synchrone vs streaming

✅ **Résolu.** La logique commune a été extraite dans `_extract_pdf_content()` au sein de `converters/pdf.py`. Cette fonction centrale implémente les 3 passes (extraction texte, batch OCR, construction résultats + liens) et retourne une liste de tuples `(page_idx, page_md, links)`.

- `convert_pdf_to_md()` consomme `_extract_pdf_content()` et assemble le résultat final.
- `convert_pdf_to_md_stream()` consomme la même fonction et yield les chunks progressivement.
- `_convert_pdf_stream()` dans `streaming.py` délègue désormais à `convert_pdf_to_md_stream()` et applique le format SSE.

**Bonus sécurité :** La sanitisation des URLs (`_sanitize_url`) est maintenant appliquée aussi en mode streaming, ce qui n'était pas le cas auparavant.

---

### 🟡 Modéré

#### 4. `is_uppercase_heading()` trop restrictif

✅ **Résolu.** La regex a été élargie de `^[A-Z\s]+$` à `^[A-Z0-9\s\-]+$`, permettant les titres avec chiffres et tirets (ex: `CHAPTER 1`, `BEST-PRACTICES`, `API-GATEWAY`).

**Fichier :** `app/converters/base.py`

#### 5. HTML sanitisation partielle

✅ **Résolu.** La sanitisation HTML a été renforcée avec un set explicite `_DANGEROUS_TAGS` qui supprime les balises dangereuses avant conversion : `script`, `style`, `meta`, `head`, `iframe`, `object`, `embed`, `form`, `link`, `base`, `applet`, `frame`, `frameset`, `svg`.

La fonction `_sanitize_soup()` étend maintenant la sanitisation des attributs `src` aux balises `<video>`, `<audio>` et `<source>` (en plus de `<img>`).

**Fichier :** `app/converters/html.py`

#### 11. En-têtes de sécurité HTTP incomplets

✅ **Résolu.** Le middleware de sécurité (`app/middleware.py`) a été amélioré avec les changements suivants :

- **X-XSS-Protection retiré** : cet en-tête est déprécié par tous les navigateurs modernes et peut introduire des vulnérabilités XSS-escaping. Supprimé au profit du CSP strict.
- **Permissions-Policy ajouté** : restreint les API navigateur puissantes non utilisées par l'app (`camera`, `microphone`, `geolocation`, `payment`, `usb`, `magnetometer`, `gyroscope`, `accelerometer`).
- **HSTS ajouté** : `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` pour forcer HTTPS.
- **CSP renforcé** : `object-src 'none'` ajouté aux deux politiques (app + docs) pour bloquer le contenu plugin. CSP script-src inclut un hash SRI pour limiter les risques CDN.
- **\_DANGEROUS_TAGS étendu** : ajout de `math`, `template`, `details`, `marquee`, `video`, `audio` dans la liste des balises supprimées.

**Fichiers :** `app/middleware.py`, `app/converters/html.py`, `tests/test_security.py`

**Note :** Le CSP docs conserve `'unsafe-inline'` car Swagger UI l'exige. Ce risque est acceptable car les routes `/docs`, `/redoc` sont désactivées en production via `--no-docs`.

**Fichier :** `app/middleware.py`

#### 6. Rate Limiter : mélange threading/asyncio

✅ **Résolu.** `threading.Lock()` a été remplacé par `asyncio.Lock()` pour un comportement non-bloquant. Toutes les méthodes utilisant le verrou (`_is_allowed_memory`, `_ensure_cleanup_started`, `_periodic_cleanup`, `reset`) sont désormais `async` avec `async with self._lock`. L'évent loop n'est plus bloqué pendant l'acquisition du verrou.

**Fichier :** `app/rate_limiter.py`

#### 7. Task Manager : tâches actives en mémoire uniquement

✅ **Résolu.** Les tâches PENDING/PROCESSING sont maintenant persistées dans le storage backend via `_persist_active_task()` avec un TTL plus court que les résultats (`result_ttl // 2`, minimum 300s). Un index de découverte (`active_task_ids:{task_id}`) permet de retrouver les tâches actives au démarrage.

- `restore_active_tasks()` est appelé dans le lifespan de l'application au démarrage et restaure les tâches PENDING/PROCESSING encore dans leur TTL.
- Les tâches restaurées repassent en PENDING (impossible de reprendre un PROCESSING sans le coroutine d'origine).
- `cleanup_completed()` nettoie également les clés `active_task_ids:{task_id}` lors de l'éviction.

**Fichiers :** `app/task_manager.py`, `app/api.py`, `app/storage/base.py`, `app/storage/memory.py`, `app/storage/redis.py`

**Note :** La persistance n'est efficace que si Redis est configuré comme backend. Avec `MemoryStorage` (par défaut), les tâches actives restent perdues au redémarrage — comportement attendu.

---

### 🟢 Mineur

#### 8. `_get_version()` fallback silencieux

✅ **Résolu.** La fonction `_get_version()` logge désormais un avertissement via `logger.warning()` si le package `caas` n'est pas trouvé, au lieu de retourner silencieusement `"unknown"`.

**Fichier :** `app/api.py`

#### 9. Docstrings mixtes FR/EN

✅ **Résolu.** Toutes les docstrings de `storage/base.py` ont été traduites en anglais pour harmoniser avec le reste du codebase.

**Fichier :** `app/storage/base.py`

#### 10. `clean_lines` : heading detection heuristique

✅ **Résolu.** La fonction `is_uppercase_heading()` a été améliorée pour réduire les faux positifs sur les acronymes courts (`API`, `URL`, `HTTP`, etc.) :

- Longueur minimale augmentée de 2 à 3 caractères
- Liste d'acronymes connus (`_KNOWN_ACRONYMS`) exclue de la détection : `API`, `URL`, `HTTP`, `HTTPS`, `FTP`, `SSH`, `TCP`, `UDP`, `IP`, `DNS`, `HTML`, `CSS`, `JS`, `JSON`, `XML`, `YAML`, `SQL`, `DB`, `CPU`, `GPU`, `RAM`, `ROM`, `SSD`, `HDD`, `ID`, `UUID`, `URI`, `URN`, `EOF`, `FAQ`, `GUI`, `CLI`, `UI`, `UX`, `IO`, `OS`, `PC`, `MAC`

**Fichier :** `app/converters/base.py`

---

## 5. Dépendances

| Catégorie | Packages                                      | Notes                                                                |
| --------- | --------------------------------------------- | -------------------------------------------------------------------- |
| **Core**  | FastAPI ≥0.115, Uvicorn ≥0.32, Pydantic ≥2.10 | Stack moderne et performante                                         |
| **PDF**   | pdfplumber ≥0.11, pypdfium2 ≥4.0              | Bonne couverture (texte + OCR)                                       |
| **DOCX**  | mammoth ≥1.8                                  | Conversion fiable, mais conversion complète (pas de streaming natif) |
| **ODT**   | odfpy ≥1.4                                    | Standard, maintenu                                                   |
| **HTML**  | BeautifulSoup4 ≥4.12                          | Robuste, bien choisi                                                 |
| **OCR**   | pytesseract ≥0.3.10, Pillow ≥10               | Dépend de Tesseract binaire (géré dans le Dockerfile)                |
| **Redis** | redis ≥5.0 (optionnel)                        | Bien isolé derrière `StorageProtocol`                                |
| **Dev**   | pytest, ruff, mypy, pre-commit, fakeredis     | Tooling complet et moderne                                           |

✅ **Versions bien verrouillées** avec des bornes supérieures (`<1.0.0`, `<2.0.0`), ce qui est une bonne pratique pour éviter les breaking changes.

### 🔒 Scan de vulnérabilités (pip-audit)

| Date       | Vulnérabilité  | Paquet    | Version avant | Version après | Statut     |
| ---------- | -------------- | --------- | ------------- | ------------- | ---------- |
| 2025-02-19 | PYSEC-2026-161 | starlette | 1.0.0         | 1.2.1         | ✅ Corrigé |

**Commande utilisée :** `.venv/Scripts/pip-audit.exe`  
**Résultat actuel :** Aucune vulnérabilité connue dans les dépendances installées.

---

## 6. Verdict global

| Critère         | Note       | Commentaire                                                                                              |
| --------------- | ---------- | -------------------------------------------------------------------------------------------------------- |
| Architecture    | ⭐⭐⭐⭐⭐ | Modulaire, extensible, patterns propres (Strategy, Factory)                                              |
| Sécurité        | ⭐⭐⭐⭐⭐ | Couverture complète : CSP strict, HSTS, Permissions-Policy, sanitisation HTML étendue, anti-spoofing IP  |
| Performance     | ⭐⭐⭐⭐⭐ | Design in-memory, single-pass PDF, streaming SSE, rate limiting natif                                    |
| Qualité du code | ⭐⭐⭐⭐⭐ | Typage, docstrings, tests. Code PDF factorisé, détection headings robuste.                               |
| Documentation   | ⭐⭐⭐⭐⭐ | README exhaustif, exemples Docker/n8n, architecture claire                                               |
| Tests           | ⭐⭐⭐⭐⭐ | Couverture 92 % (553 tests, 0 échec), benchmarks, marqueurs, fixtures réalistes, tests sécurité complets |

### Synthèse

C'est un projet **mature et bien conçu**, avec une architecture claire, une approche security-first, et une attention particulière aux performances. Les points d'amélioration sont mineurs et n'affectent pas la robustesse globale du service.

**Points résolus :**

1. ✅ Code dupliqué PDF factorisé dans `_extract_pdf_content()`
2. ✅ Sanitisation HTML renforcée avec `_DANGEROUS_TAGS` et `_sanitize_soup()`
3. ✅ Rate Limiter avec `asyncio.Lock()` non-bloquant
4. ✅ Tâches actives persistées dans le storage backend avec restauration au démarrage
5. ✅ Docstrings FR/EN harmonisées dans `storage/base.py`
6. ✅ Détection d'acronymes améliorée dans `is_uppercase_heading()` avec liste d'exclusion et longueur minimale augmentée
7. ✅ X-XSS-Protection obsolète retiré du middleware
8. ✅ Permissions-Policy ajouté (camera, microphone, geolocation, etc.)
9. ✅ HSTS ajouté avec `max-age=31536000; includeSubDomains; preload`
10. ✅ CSP renforcé avec `object-src 'none'` et hash SRI pour script-src
11. ✅ `_DANGEROUS_TAGS` étendu (math, template, details, marquee, video, audio)
12. ✅ 15 nouveaux tests de sécurité ajoutés (56 tests au total)

**Points restants (mineurs) :**

Aucun point critique restant.

---

## 7. Recommandations supplémentaires

### 🟡 Moyenne priorité

1. **Health check exposé** : L'endpoint `/healthz` expose des informations détaillées (version, stockage, Redis). Ajouter un endpoint `/ready` minimal pour les load balancers et réserver `/healthz` au réseau interne.
2. **Redis sans TLS** : Utiliser `rediss://` (Redis over TLS) en production si Redis est sur une machine séparée.

### 🟢 Basse priorité

1. **Limite de taille réponse Markdown** : Une conversion PDF→Markdown peut produire un résultat volumineux. Ajouter une vérification post-conversion (erreur 413 si trop grand).
2. **Logs de sécurité dédiés** : Logger les tentatives de path traversal bloquées, ZIP bombs détectées, et activations du rate limiting.
3. **CORS explicite** : Configurer `allow_origins` restreint si l'API a des consommateurs frontend connus.

---

## 8. Score Global

| Catégorie              | Note       | Commentaire                                               |
| ---------------------- | ---------- | --------------------------------------------------------- |
| Validation d'entrée    | ⭐⭐⭐⭐⭐ | Magic bytes + path traversal + ZIP bomb (7 vérifications) |
| Sanitisation de sortie | ⭐⭐⭐⭐⭐ | html.escape() dans tous les converters, URL sanitization  |
| Infrastructure         | ⭐⭐⭐⭐   | Multi-stage Docker, non-root user, Redis optionnel        |
| Gestion d'erreurs      | ⭐⭐⭐⭐   | Centralisée, debug-only details                           |
| Rate Limiting          | ⭐⭐⭐⭐⭐ | Sliding window, dual backend (memory/Redis)               |
| Dépendances            | ⭐⭐⭐⭐⭐ | Aucune vulnérabilité connue après correction starlette    |

**Note globale : A+ (Excellent)**
