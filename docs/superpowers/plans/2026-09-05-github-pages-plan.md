# AstroChecker GitHub Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pubblicare una pagina GitHub Pages pubblica che descriva AstroChecker e la release corrente.

**Architecture:** Un singolo `docs/index.html` statico contiene markup e stile, senza dipendenze runtime. Un workflow GitHub Actions carica `docs/` come artefatto Pages e lo pubblica su `main`.

**Tech Stack:** HTML5, CSS3, GitHub Actions Pages.

**Spec:** `docs/superpowers/specs/2026-09-05-github-pages-design.md`

## Global Constraints

- Nessun framework, CDN, JavaScript applicativo o raccolta dati.
- Il sito deve descrivere solo comportamenti verificati della `v0.3.0-alpha.2`.
- Layout responsive, contrasto leggibile e focus visibile.

---

### Task 1: Pagina pubblica

**Files:**
- Create: `docs/index.html`
- Test: verifica locale con browser headless e controllo di link/testi obbligatori.

- [ ] **Step 1: Create the page**

  Realizzare hero, requisiti, flusso, risultati, dati, limiti, avvio e release con CSS nello stesso file.

- [ ] **Step 2: Verify the page locally**

  Servire `docs/` con un server statico Python e controllare con Playwright titolo, sezioni, link GitHub, assenza di errori JavaScript e assenza di overflow a 390 e 1440 pixel.

### Task 2: Deploy GitHub Pages

**Files:**
- Create: `.github/workflows/pages.yml`

- [ ] **Step 1: Add the workflow**

  Usare le action ufficiali `configure-pages`, `upload-pages-artifact` e `deploy-pages`, con permessi `pages: write` e `id-token: write`, pubblicando `docs/` su push a `main`.

- [ ] **Step 2: Validate configuration**

  Controllare YAML, verificare che il workflow punti a `docs/` e avviare il workflow tramite GitHub dopo il push.

### Task 3: Release e handoff

**Files:**
- Modify: `README.md` con il link alla pagina pubblica.

- [ ] **Step 1: Add the public link**

  Inserire il link Pages in posizione visibile nel README senza duplicare la documentazione tecnica.

- [ ] **Step 2: Commit, push and verify**

  Verificare i test, creare commit con l’identità dell’utente, pushare il branch su `main`, attendere il workflow e controllare l’URL pubblico con una richiesta HTTP.
