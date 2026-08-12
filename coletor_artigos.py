# -*- coding: utf-8 -*-
"""
coletor_artigos.py — Busca federada e triagem editorial de literatura biomédica
Jornal Cienc.IA · coletor biomédico · versão 4.3

O coletor usa PubMed, Europe PMC e, quando houver credenciais/entitlement, Embase como
fontes de DESCOBERTA biomédica. Semantic Scholar, OpenAlex e Crossref são usados apenas
para ENRIQUECIMENTO de registros já descobertos nas fontes biomédicas; eles não introduzem
artigos novos na fila editorial.
O pipeline deduplica os resultados e produz uma lista de prioridade editorial. O número final NÃO é
apresentado como "qualidade científica" ou "nível de evidência". Ele combina
sinais operacionais distintos para ajudar o revisor a decidir o que ler primeiro:

  - desenho do estudo identificado nos metadados;
  - atualidade;
  - impacto bibliométrico atenuado por logaritmo;
  - disponibilidade de texto aberto;
  - ordem de relevância fornecida pelas fontes.

OCEBM é usado apenas como referência conceitual para descrever desenhos de
estudo. A própria OCEBM recomenda julgamento clínico e interpretação conforme
a pergunta de pesquisa; portanto, uma revisão narrativa não é tratada como
sinônimo de revisão sistemática nem como evidência máxima.

Uso:
    python coletor_artigos.py
    python coletor_artigos.py --temas "diet liver disease" "vaccine safety"
    python coletor_artigos.py
    python coletor_artigos.py --limite-busca 300
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("coletor")

S2_KEY = os.getenv("SEMANTIC_SCHOLAR_KEY", "")
EMBASE_API_KEY = os.getenv("EMBASE_API_KEY", "").strip()
EMBASE_INSTTOKEN = os.getenv("EMBASE_INSTTOKEN", "").strip()
ATIVAR_EMBASE = os.getenv("ATIVAR_EMBASE", "1").strip() != "0"
NCBI_KEY = os.getenv("NCBI_API_KEY", "")
ATIVAR_ENRIQUECIMENTO = os.getenv("ATIVAR_ENRIQUECIMENTO", "1").strip() != "0"
EMAIL = os.getenv("USER_EMAIL", "contato@example.com")
ANO_ATUAL = datetime.now().year

# Limiar editorial fixo do projeto. Todos os artigos elegíveis com score >= 60 entram.
MIN_PRIORIDADE_EDITORIAL = 60.0

TEMAS_PADRAO = [
    "sunscreen skin cancer prevention",
    "cancer alternative medicine treatment",
    "nutrition diet health outcomes",
    "influenza transmission cold weather",
    "red meat processed food cancer risk",
    "vaccine safety adverse effects",
    "sugar consumption mental health anxiety",
    "ivermectin antiparasitic clinical use",
    "egg cholesterol cardiovascular disease",
    "detox diet liver kidney health",
]

S2_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
OPENALEX_URL = "https://api.openalex.org/works"
CROSSREF_URL = "https://api.crossref.org/works"
EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EMBASE_URL = "https://api.elsevier.com/content/embase/article"

S2_CAMPOS = ",".join(
    [
        "paperId",
        "title",
        "abstract",
        "year",
        "authors",
        "citationCount",
        "influentialCitationCount",
        "publicationTypes",
        "isRetracted",
        "isOpenAccess",
        "openAccessPdf",
        "externalIds",
        "venue",
    ]
)

# Peso editorial aproximado por desenho. Não representa um nível OCEBM automático.
PESO_DESENHO = {
    "SystematicReview": 50,
    "MetaAnalysis": 50,
    "RCT": 45,
    "ClinicalTrial": 40,
    "CohortStudy": 35,
    "CaseControlStudy": 32,
    "ObservationalStudy": 28,
    "Review": 25,
    "JournalArticle": 22,
    "journal-article": 22,
    "CaseSeries": 15,
    "CaseReport": 10,
    "Editorial": 5,
    "Opinion": 5,
    "Letter": 5,
    "preprint": 12,
    "Conference": 12,
    "proceedings-article": 12,
    "book-chapter": 8,
}

ROTULO_DESENHO = {
    "SystematicReview": "Revisão sistemática",
    "MetaAnalysis": "Meta-análise",
    "RCT": "Ensaio clínico randomizado",
    "ClinicalTrial": "Ensaio clínico",
    "CohortStudy": "Estudo de coorte",
    "CaseControlStudy": "Estudo caso-controle",
    "ObservationalStudy": "Estudo observacional",
    "Review": "Artigo de revisão",
    "JournalArticle": "Artigo científico",
    "journal-article": "Artigo científico",
    "CaseSeries": "Série de casos",
    "CaseReport": "Relato de caso",
    "Editorial": "Editorial",
    "Opinion": "Opinião",
    "Letter": "Carta",
    "preprint": "Preprint",
    "Conference": "Artigo de conferência",
    "proceedings-article": "Artigo de conferência",
    "book-chapter": "Capítulo de livro",
}


def _normalizar_doi(doi: str) -> str:
    doi = (doi or "").strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi.lower()


def _texto_xml(elemento: Optional[ET.Element]) -> str:
    if elemento is None:
        return ""
    return "".join(elemento.itertext()).strip()


def _nomes(lista: Iterable[Dict], max_n: int = 3) -> str:
    itens = list(lista)
    nomes = [a.get("name", "").strip() for a in itens[:max_n]]
    if len(itens) > max_n:
        nomes.append("et al.")
    return "; ".join(n for n in nomes if n)


def _artigo(
    *,
    paper_id: str,
    doi: str,
    fonte: str,
    titulo: str,
    abstract: str,
    ano: Optional[int],
    autores: str,
    cit_total: int,
    cit_influ: int,
    tipos: List[str],
    open_access: bool,
    url_pdf: str,
    url_texto_completo: str,
    url_artigo: str,
    retracted: bool = False,
    rank_fonte: int = 0,
    periodico: str = "",
) -> Dict:
    return {
        "paper_id": paper_id,
        "doi": _normalizar_doi(doi),
        "fonte": fonte,
        "titulo": (titulo or "").strip(),
        "abstract": (abstract or "").strip(),
        "ano": int(ano or ANO_ATUAL - 5),
        "autores": autores,
        "cit_total": int(cit_total or 0),
        "cit_influ": int(cit_influ or 0),
        "tipos": tipos or ["JournalArticle"],
        "retracted": bool(retracted),
        "open_access": bool(open_access),
        "url_pdf": url_pdf or "",
        "url_texto_completo": url_texto_completo or "",
        "url_artigo": url_artigo or "",
        "rank_fonte": int(rank_fonte or 0),
        "periodico": periodico or "",
    }


def classificar_desenho(tipos: List[str]) -> Tuple[str, int, str]:
    """Retorna tipo principal, peso editorial e rótulo legível."""
    tipos = tipos or ["JournalArticle"]
    principal = max(tipos, key=lambda t: PESO_DESENHO.get(t, 18))
    peso = PESO_DESENHO.get(principal, 18)
    rotulo = ROTULO_DESENHO.get(principal, principal)
    return principal, peso, rotulo


def calcular_prioridade_editorial(a: Dict) -> Dict:
    """Calcula sinais separados e um total operacional de 0 a 100."""
    principal, desenho, rotulo = classificar_desenho(a.get("tipos", []))

    idade = max(0, ANO_ATUAL - int(a.get("ano") or ANO_ATUAL))
    atualidade = max(0.0, 20.0 - 1.5 * idade)

    cit_total = max(0, int(a.get("cit_total", 0)))
    cit_influ = max(0, int(a.get("cit_influ", 0)))
    impacto = min(20.0, math.log1p(cit_total) * 3.2 + math.log1p(cit_influ) * 5.0)

    if a.get("url_pdf"):
        acesso = 10.0
        acesso_status = "PDF aberto identificado"
    elif a.get("url_texto_completo"):
        acesso = 8.0
        acesso_status = "Texto completo aberto identificado"
    elif a.get("doi"):
        acesso = 2.0
        acesso_status = "DOI disponível; acesso aberto não confirmado"
    else:
        acesso = 0.0
        acesso_status = "Texto completo não identificado"

    rank = max(0, int(a.get("rank_fonte", 0)))
    relevancia = max(0.0, 10.0 - min(rank, 20) * 0.35)

    total = min(100.0, desenho + atualidade + impacto + acesso + relevancia)
    return {
        "score_prioridade_editorial": round(total, 2),
        "componentes_prioridade": {
            "desenho": round(desenho, 2),
            "atualidade": round(atualidade, 2),
            "impacto_bibliometrico": round(impacto, 2),
            "acesso": round(acesso, 2),
            "relevancia_na_fonte": round(relevancia, 2),
        },
        "tipo_principal": principal,
        "desenho_estudo_rotulo": rotulo,
        "acesso_status": acesso_status,
        "aviso_evidencia": (
            "Classificação baseada em metadados. Não substitui avaliação crítica do "
            "método, risco de viés, pergunta clínica ou certeza da evidência."
        ),
    }


def buscar_s2(tema: str, limite: int) -> List[Dict]:
    headers = {"User-Agent": f"TCC-UFV/3.0 (mailto:{EMAIL})"}
    if S2_KEY:
        headers["x-api-key"] = S2_KEY
    params = {"query": tema, "limit": min(limite, 100), "fields": S2_CAMPOS}

    for tentativa in range(1, 5):
        try:
            r = requests.get(S2_URL, params=params, headers=headers, timeout=30)
            if r.status_code == 429:
                espera = 2**tentativa
                log.warning("  [S2] Limite de requisições. Aguardando %ss...", espera)
                time.sleep(espera)
                continue
            if r.status_code in (400, 403) and "x-api-key" in headers:
                headers.pop("x-api-key", None)
                r = requests.get(S2_URL, params=params, headers=headers, timeout=30)
            r.raise_for_status()
            artigos = []
            for rank, p in enumerate(r.json().get("data", [])):
                ids = p.get("externalIds") or {}
                pdf = (p.get("openAccessPdf") or {}).get("url", "") or ""
                artigos.append(
                    _artigo(
                        paper_id=p.get("paperId", ""),
                        doi=ids.get("DOI", ""),
                        fonte="SemanticScholar",
                        titulo=p.get("title", ""),
                        abstract=p.get("abstract", ""),
                        ano=p.get("year"),
                        autores=_nomes(p.get("authors") or []),
                        cit_total=p.get("citationCount") or 0,
                        cit_influ=p.get("influentialCitationCount") or 0,
                        tipos=p.get("publicationTypes") or ["JournalArticle"],
                        open_access=bool(pdf),
                        url_pdf=pdf,
                        url_texto_completo=pdf,
                        url_artigo=f"https://www.semanticscholar.org/paper/{p.get('paperId', '')}",
                        retracted=bool(p.get("isRetracted")),
                        rank_fonte=rank,
                        periodico=p.get("venue") or "",
                    )
                )
            log.info("  [S2] '%s': %s artigos", tema, len(artigos))
            return artigos
        except Exception as exc:
            log.warning("  [S2] tentativa %s/4: %s", tentativa, exc)
            if tentativa < 4:
                time.sleep(2**tentativa)
    return []


def buscar_pubmed(tema: str, limite: int) -> List[Dict]:
    headers = {"User-Agent": f"TCC-UFV/3.0 (mailto:{EMAIL})"}
    search_params = {
        "db": "pubmed",
        "term": tema,
        "retmax": min(limite, 1000),
        "retmode": "json",
        "sort": "relevance",
    }
    if NCBI_KEY:
        search_params["api_key"] = NCBI_KEY

    try:
        sr = requests.get(PUBMED_SEARCH, params=search_params, headers=headers, timeout=20)
        sr.raise_for_status()
        ids = sr.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
    except Exception as exc:
        log.warning("  [PubMed] erro na busca: %s", exc)
        return []

    fetch_params = {"db": "pubmed", "id": ",".join(ids), "rettype": "xml", "retmode": "xml"}
    if NCBI_KEY:
        fetch_params["api_key"] = NCBI_KEY

    try:
        time.sleep(0.15 if NCBI_KEY else 0.36)
        fr = requests.get(PUBMED_FETCH, params=fetch_params, headers=headers, timeout=35)
        fr.raise_for_status()
        root = ET.fromstring(fr.content)
    except Exception as exc:
        log.warning("  [PubMed] erro no fetch: %s", exc)
        return []

    mapa_tipos = {
        "Systematic Review": "SystematicReview",
        "Meta-Analysis": "MetaAnalysis",
        "Randomized Controlled Trial": "RCT",
        "Controlled Clinical Trial": "ClinicalTrial",
        "Clinical Trial": "ClinicalTrial",
        "Observational Study": "ObservationalStudy",
        "Review": "Review",
        "Case Reports": "CaseReport",
        "Journal Article": "JournalArticle",
    }

    artigos: List[Dict] = []
    for rank, registro in enumerate(root.findall(".//PubmedArticle")):
        try:
            medline = registro.find(".//MedlineCitation")
            article = medline.find("Article") if medline is not None else None
            if article is None:
                continue

            titulo = _texto_xml(article.find("ArticleTitle"))
            abstract = " ".join(
                _texto_xml(p) for p in article.findall(".//Abstract/AbstractText") if _texto_xml(p)
            )

            pub = registro.find(".//PubDate")
            ano_txt = ""
            if pub is not None:
                ano_txt = pub.findtext("Year") or (pub.findtext("MedlineDate") or "")[:4]
            ano = int(ano_txt) if ano_txt.isdigit() else ANO_ATUAL - 5

            autores = []
            autor_list = article.findall(".//AuthorList/Author")
            for autor in autor_list[:3]:
                nome = f"{autor.findtext('ForeName', '')} {autor.findtext('LastName', '')}".strip()
                if nome:
                    autores.append(nome)
            if len(autor_list) > 3:
                autores.append("et al.")

            pmid = medline.findtext("PMID") or ""
            doi = ""
            pmcid = ""
            for ident in registro.findall(".//PubmedData/ArticleIdList/ArticleId"):
                if ident.get("IdType") == "doi":
                    doi = ident.text or ""
                elif ident.get("IdType") == "pmc":
                    pmcid = ident.text or ""

            tipos_brutos = [
                (pt.text or "").strip() for pt in article.findall(".//PublicationTypeList/PublicationType")
            ]
            tipos = [mapa_tipos[t] for t in tipos_brutos if t in mapa_tipos] or ["JournalArticle"]

            periodico = article.findtext(".//Journal/Title") or ""
            url_artigo = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            url_completo = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else ""

            artigos.append(
                _artigo(
                    paper_id=f"pmid_{pmid}",
                    doi=doi,
                    fonte="PubMed",
                    titulo=titulo,
                    abstract=abstract,
                    ano=ano,
                    autores="; ".join(autores),
                    cit_total=0,
                    cit_influ=0,
                    tipos=tipos,
                    open_access=bool(pmcid),
                    url_pdf="",
                    url_texto_completo=url_completo,
                    url_artigo=url_artigo,
                    rank_fonte=rank,
                    periodico=periodico,
                )
            )
        except Exception as exc:
            log.debug("  [PubMed] registro ignorado: %s", exc)

    log.info("  [PubMed] '%s': %s artigos", tema, len(artigos))
    return artigos


def buscar_europe_pmc(tema: str, limite: int) -> List[Dict]:
    """Busca biomédica complementar no Europe PMC.

    Europe PMC é tratado como fonte de descoberta, ao lado do PubMed. A consulta
    exige abstract para evitar encaminhar ao revisor registros sem fonte textual.
    """
    params = {
        "query": f"({tema}) AND HAS_ABSTRACT:Y",
        "format": "json",
        "resultType": "core",
        "pageSize": min(limite, 1000),
    }
    headers = {"User-Agent": f"TCC-UFV/4.2 (mailto:{EMAIL})"}
    try:
        r = requests.get(EUROPE_PMC_URL, params=params, headers=headers, timeout=35)
        r.raise_for_status()
        dados = r.json()
    except Exception as exc:
        log.warning("  [Europe PMC] erro: %s", exc)
        return []

    mapa_tipos = {
        "systematic review": "SystematicReview",
        "meta-analysis": "MetaAnalysis",
        "meta analysis": "MetaAnalysis",
        "randomized controlled trial": "RCT",
        "randomised controlled trial": "RCT",
        "clinical trial": "ClinicalTrial",
        "observational study": "ObservationalStudy",
        "review": "Review",
        "case reports": "CaseReport",
        "case report": "CaseReport",
        "journal article": "JournalArticle",
        "editorial": "Editorial",
        "letter": "Letter",
    }

    artigos: List[Dict] = []
    resultados = (dados.get("resultList") or {}).get("result") or []
    for rank, item in enumerate(resultados):
        try:
            titulo = (item.get("title") or "").strip()
            abstract = (item.get("abstractText") or "").strip()
            if not titulo or not abstract:
                continue

            pmid = str(item.get("pmid") or "").strip()
            pmcid = str(item.get("pmcid") or "").strip()
            doi = _normalizar_doi(str(item.get("doi") or ""))
            ano_txt = str(item.get("pubYear") or "")
            ano = int(ano_txt[:4]) if ano_txt[:4].isdigit() else ANO_ATUAL - 5
            tipos_raw = (item.get("pubTypeList") or {}).get("pubType") or []
            if isinstance(tipos_raw, str):
                tipos_raw = [tipos_raw]
            tipos = []
            for tipo in tipos_raw:
                chave = str(tipo or "").strip().lower()
                if chave in mapa_tipos:
                    tipos.append(mapa_tipos[chave])
            if not tipos:
                tipos = ["JournalArticle"]

            retratado = bool(item.get("isRetracted", False)) or any(
                "retract" in str(tipo).lower() for tipo in tipos_raw
            )
            oa = str(item.get("isOpenAccess") or "").upper() == "Y" or bool(pmcid)
            url_artigo = ""
            if pmid:
                url_artigo = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            elif doi:
                url_artigo = f"https://doi.org/{doi}"
            elif item.get("id"):
                url_artigo = f"https://europepmc.org/article/{item.get('source','MED')}/{item.get('id')}"
            url_completo = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else ""

            paper_id = f"pmid_{pmid}" if pmid else (f"epmc_{item.get('source','')}_{item.get('id','')}".strip("_"))
            artigos.append(
                _artigo(
                    paper_id=paper_id,
                    doi=doi,
                    fonte="EuropePMC",
                    titulo=titulo,
                    abstract=abstract,
                    ano=ano,
                    autores=(item.get("authorString") or "").strip(),
                    cit_total=int(item.get("citedByCount") or 0),
                    cit_influ=0,
                    tipos=tipos,
                    open_access=oa,
                    url_pdf="",
                    url_texto_completo=url_completo,
                    url_artigo=url_artigo,
                    retracted=retratado,
                    rank_fonte=rank,
                    periodico=(item.get("journalTitle") or "").strip(),
                )
            )
        except Exception as exc:
            log.debug("  [Europe PMC] registro ignorado: %s", exc)

    log.info("  [Europe PMC] '%s': %s artigos", tema, len(artigos))
    return artigos



def _embase_texto(obj) -> str:
    """Extrai texto de campos que podem vir como string, lista ou dicionário."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, list):
        partes = [_embase_texto(x) for x in obj]
        return " ".join(x for x in partes if x).strip()
    if isinstance(obj, dict):
        for chave in ("para", "ttltext", "content", "$", "text"):
            if chave in obj:
                txt = _embase_texto(obj.get(chave))
                if txt:
                    return txt
    return ""


def _embase_tipos(registro: Dict) -> List[str]:
    """Converte descritores/citation type do Embase para os tipos editoriais do projeto."""
    termos: List[str] = []
    head = registro.get("head") or {}
    citation = ((head.get("citationInfo") or {}).get("citationType") or [])
    for item in citation if isinstance(citation, list) else [citation]:
        txt = _embase_texto(item).lower()
        if txt:
            termos.append(txt)

    descriptors = (((head.get("enhancement") or {}).get("descriptors")) or [])
    for grupo in descriptors if isinstance(descriptors, list) else [descriptors]:
        for desc in (grupo or {}).get("descriptor", []) or []:
            txt = _embase_texto((desc or {}).get("mainterm")).lower()
            if txt:
                termos.append(txt)

    mapa = [
        ("systematic review", "SystematicReview"),
        ("meta analysis", "MetaAnalysis"),
        ("meta-analysis", "MetaAnalysis"),
        ("randomized controlled trial", "RCT"),
        ("randomised controlled trial", "RCT"),
        ("controlled clinical trial", "ClinicalTrial"),
        ("clinical trial", "ClinicalTrial"),
        ("cohort analysis", "CohortStudy"),
        ("cohort study", "CohortStudy"),
        ("case control study", "CaseControlStudy"),
        ("case-control study", "CaseControlStudy"),
        ("observational study", "ObservationalStudy"),
        ("case report", "CaseReport"),
        ("review", "Review"),
        ("editorial", "Editorial"),
        ("letter", "Letter"),
        ("article", "JournalArticle"),
    ]
    encontrados: List[str] = []
    texto = " | ".join(termos)
    for termo, tipo in mapa:
        if termo in texto and tipo not in encontrados:
            encontrados.append(tipo)
    return encontrados or ["JournalArticle"]


def _parse_embase_result(registro: Dict, rank: int) -> Optional[Dict]:
    """Normaliza um resultado do Embase para o esquema comum do coletor."""
    try:
        item_info = registro.get("itemInfo") or {}
        ids = item_info.get("itemIdList") or {}
        head = registro.get("head") or {}

        titulo = ""
        titulos = ((head.get("citationTitle") or {}).get("titleText") or [])
        if isinstance(titulos, list) and titulos:
            titulo = _embase_texto(titulos[0])
        titulo = titulo or _embase_texto(registro.get("title"))

        abstracts = ((head.get("abstracts") or {}).get("abstracts") or [])
        abstract = " ".join(
            _embase_texto(x) for x in (abstracts if isinstance(abstracts, list) else [abstracts])
            if _embase_texto(x)
        ).strip()

        source = head.get("source") or {}
        ano_raw = source.get("publicationYear") or registro.get("publicationYear")
        try:
            ano = int(ano_raw) if ano_raw else None
        except Exception:
            ano = None

        autores_lista = ((head.get("authorList") or {}).get("authors") or [])
        autores = []
        for a in autores_lista if isinstance(autores_lista, list) else []:
            nome = " ".join(x for x in [(a or {}).get("initials", ""), (a or {}).get("surname", "")] if x).strip()
            if nome:
                autores.append(nome)
        if len(autores) > 3:
            autores = autores[:3] + ["et al."]

        embase_id = str(ids.get("embase") or ids.get("lui") or ids.get("pui") or "")
        doi = str(ids.get("doi") or "")
        url = _embase_texto((registro.get("openLink") or {}).get("openUrl"))
        periodico = _embase_texto(source.get("sourceTitle")) or _embase_texto(source.get("sourceTitleAbbrev"))
        termos = " ".join(
            _embase_texto((d or {}).get("mainterm"))
            for g in (((head.get("enhancement") or {}).get("descriptors")) or [])
            for d in ((g or {}).get("descriptor") or [])
        ).lower()
        retracted = "retracted article" in termos or "retraction" in termos

        return _artigo(
            paper_id=f"embase:{embase_id}" if embase_id else f"embase:{rank}:{_normalizar_doi(doi)}",
            doi=doi,
            fonte="Embase",
            titulo=titulo,
            abstract=abstract,
            ano=ano,
            autores="; ".join(autores),
            cit_total=0,
            cit_influ=0,
            tipos=_embase_tipos(registro),
            open_access=False,
            url_pdf="",
            url_texto_completo="",
            url_artigo=url,
            retracted=retracted,
            rank_fonte=rank,
            periodico=periodico,
        )
    except Exception as exc:
        log.debug("  [Embase] falha ao normalizar registro: %s", exc)
        return None


def _embase_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/json",
        "X-ELS-APIKey": EMBASE_API_KEY,
        "User-Agent": f"TCC-UFV/4.2 (mailto:{EMAIL})",
    }
    if EMBASE_INSTTOKEN:
        headers["X-ELS-Insttoken"] = EMBASE_INSTTOKEN
    return headers


def _buscar_detalhe_embase(embase_id: str) -> Optional[Dict]:
    if not embase_id:
        return None
    try:
        r = requests.get(
            f"{EMBASE_URL}/embase/{embase_id}",
            headers=_embase_headers(),
            timeout=30,
        )
        if r.status_code != 200:
            return None
        dados = r.json()
        resultados = dados.get("results") or []
        return resultados[0] if resultados else None
    except Exception:
        return None


def buscar_embase(tema: str, limite: int) -> List[Dict]:
    """Busca Embase quando API key e entitlement institucional estiverem disponíveis.

    A API key nunca deve ser escrita no código ou no JSON de saída. Ela é lida de
    EMBASE_API_KEY no .env. EMBASE_INSTTOKEN é opcional e só deve ser usado quando
    fornecido/autorizado pela instituição ou pela Elsevier.
    """
    if not ATIVAR_EMBASE:
        return []
    if not EMBASE_API_KEY:
        log.info("  [Embase] desativado: EMBASE_API_KEY não configurada no .env")
        return []

    artigos: List[Dict] = []
    start = 1
    # Lotes pequenos tornam o cliente compatível com diferentes limites de serviço.
    while len(artigos) < limite:
        count = min(50, limite - len(artigos))
        params = {
            "query": tema,
            "start": start,
            "count": count,
            "sort": "relevance",
        }
        try:
            r = requests.get(EMBASE_URL, params=params, headers=_embase_headers(), timeout=40)
            if r.status_code == 401:
                log.warning("  [Embase] API key ausente/inválida (HTTP 401).")
                return []
            if r.status_code == 403:
                log.warning(
                    "  [Embase] acesso negado (HTTP 403). A chave pode existir, mas a API "
                    "requer entitlement Embase da instituição; teste na rede/VPN institucional "
                    "ou solicite o insttoken à biblioteca/Elsevier."
                )
                return []
            if r.status_code == 429:
                log.warning("  [Embase] quota temporariamente excedida (HTTP 429).")
                return artigos
            r.raise_for_status()
            dados = r.json()
        except Exception as exc:
            log.warning("  [Embase] erro na busca: %s", exc)
            return artigos

        resultados = dados.get("results") or []
        if not resultados:
            break

        for local_rank, registro in enumerate(resultados):
            rank = start - 1 + local_rank
            art = _parse_embase_result(registro, rank)
            if art and not art.get("abstract"):
                ids = ((registro.get("itemInfo") or {}).get("itemIdList") or {})
                embase_id = str(ids.get("embase") or "")
                detalhe = _buscar_detalhe_embase(embase_id)
                if detalhe:
                    art_detalhe = _parse_embase_result(detalhe, rank)
                    if art_detalhe:
                        art = _mesclar_registros(art, art_detalhe)
            if art:
                artigos.append(art)
            if len(artigos) >= limite:
                break

        if len(resultados) < count:
            break
        start += len(resultados)
        time.sleep(0.12)

    log.info("  [Embase] '%s': %s artigos", tema, len(artigos))
    return artigos


def testar_acesso_embase() -> bool:
    """Faz uma consulta mínima sem imprimir ou registrar a chave secreta."""
    if not EMBASE_API_KEY:
        print("Embase: EMBASE_API_KEY não está configurada no .env.")
        return False
    try:
        r = requests.get(
            EMBASE_URL,
            params={"query": "migraine", "start": 1, "count": 1, "sort": "relevance"},
            headers=_embase_headers(),
            timeout=30,
        )
        if r.status_code == 200:
            dados = r.json()
            hits = (dados.get("header") or {}).get("hits")
            print(f"Embase: acesso à API confirmado. Resultados encontrados: {hits if hits is not None else 'sim'}.")
            return True
        if r.status_code == 401:
            print("Embase: HTTP 401 — API key inválida ou não reconhecida.")
        elif r.status_code == 403:
            print("Embase: HTTP 403 — a API key foi enviada, mas falta entitlement institucional para Embase. Tente pela rede/VPN da UFV ou solicite insttoken/acesso de API à biblioteca/Elsevier.")
        elif r.status_code == 429:
            print("Embase: HTTP 429 — quota da API excedida temporariamente.")
        else:
            print(f"Embase: HTTP {r.status_code} — acesso não confirmado.")
        return False
    except Exception as exc:
        print(f"Embase: não foi possível testar a API: {exc}")
        return False


def _reconstruir_abstract_openalex(inv: Dict) -> str:
    if not inv:
        return ""
    max_pos = max(p for posicoes in inv.values() for p in posicoes) + 1
    palavras = [""] * max_pos
    for palavra, posicoes in inv.items():
        for pos in posicoes:
            palavras[pos] = palavra
    return " ".join(palavras).strip()


def buscar_openalex(tema: str, limite: int) -> List[Dict]:
    params = {
        "search": tema,
        "filter": "type:article",
        "sort": "relevance_score:desc",
        "per-page": min(limite, 200),
        "select": (
            "id,doi,title,abstract_inverted_index,publication_year,authorships,"
            "cited_by_count,type,open_access,best_oa_location,primary_location"
        ),
        "mailto": EMAIL,
    }
    try:
        r = requests.get(
            OPENALEX_URL,
            params=params,
            headers={"User-Agent": f"TCC-UFV/3.0 (mailto:{EMAIL})"},
            timeout=30,
        )
        r.raise_for_status()
    except Exception as exc:
        log.warning("  [OpenAlex] erro: %s", exc)
        return []

    mapa_tipos = {
        "article": "JournalArticle",
        "review": "Review",
        "book-chapter": "book-chapter",
        "preprint": "preprint",
        "proceedings-article": "Conference",
    }

    artigos = []
    for rank, w in enumerate(r.json().get("results", [])):
        doi = _normalizar_doi(w.get("doi") or "")
        best_oa = w.get("best_oa_location") or {}
        pdf = best_oa.get("pdf_url") or ""
        landing = best_oa.get("landing_page_url") or ""
        oa = bool((w.get("open_access") or {}).get("is_oa", False))

        autores_raw = w.get("authorships") or []
        nomes = [a.get("author", {}).get("display_name", "") for a in autores_raw[:3]]
        if len(autores_raw) > 3:
            nomes.append("et al.")

        primary = w.get("primary_location") or {}
        source = primary.get("source") or {}
        periodico = source.get("display_name") or ""
        oa_id = (w.get("id") or "").replace("https://openalex.org/", "")

        artigos.append(
            _artigo(
                paper_id=f"oa_{oa_id}",
                doi=doi,
                fonte="OpenAlex",
                titulo=w.get("title", ""),
                abstract=_reconstruir_abstract_openalex(w.get("abstract_inverted_index") or {}),
                ano=w.get("publication_year"),
                autores="; ".join(n for n in nomes if n),
                cit_total=w.get("cited_by_count") or 0,
                cit_influ=0,
                tipos=[mapa_tipos.get(w.get("type") or "article", "JournalArticle")],
                open_access=oa,
                url_pdf=pdf,
                url_texto_completo=landing,
                url_artigo=f"https://doi.org/{doi}" if doi else w.get("id", ""),
                rank_fonte=rank,
                periodico=periodico,
            )
        )

    log.info("  [OpenAlex] '%s': %s artigos", tema, len(artigos))
    return artigos


def buscar_crossref(tema: str, limite: int) -> List[Dict]:
    params = {
        "query": tema,
        "rows": min(limite, 100),
        "sort": "relevance",
        "order": "desc",
        "select": "DOI,title,abstract,type,is-referenced-by-count,published,author,container-title",
    }
    try:
        r = requests.get(
            CROSSREF_URL,
            params=params,
            headers={"User-Agent": f"TCC-UFV/3.0 (mailto:{EMAIL})"},
            timeout=25,
        )
        r.raise_for_status()
    except Exception as exc:
        log.warning("  [Crossref] erro: %s", exc)
        return []

    artigos = []
    for rank, item in enumerate(r.json().get("message", {}).get("items", [])):
        abstract = re.sub(r"<[^>]+>", " ", item.get("abstract", ""))
        abstract = re.sub(r"\s+", " ", abstract).strip()
        titulo_lista = item.get("title") or []
        titulo = titulo_lista[0] if titulo_lista else ""
        partes = item.get("published", {}).get("date-parts", [[]])
        ano = partes[0][0] if partes and partes[0] else ANO_ATUAL - 5
        autores_raw = item.get("author") or []
        nomes = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in autores_raw[:3]]
        if len(autores_raw) > 3:
            nomes.append("et al.")
        doi = item.get("DOI", "")
        periodicos = item.get("container-title") or []

        artigos.append(
            _artigo(
                paper_id=f"crossref_{doi}" if doi else f"crossref_{abs(hash(titulo))}",
                doi=doi,
                fonte="Crossref",
                titulo=titulo,
                abstract=abstract,
                ano=ano,
                autores="; ".join(n for n in nomes if n),
                cit_total=item.get("is-referenced-by-count", 0),
                cit_influ=0,
                tipos=[item.get("type", "journal-article")],
                open_access=False,
                url_pdf="",
                url_texto_completo="",
                url_artigo=f"https://doi.org/{_normalizar_doi(doi)}" if doi else "",
                rank_fonte=rank,
                periodico=periodicos[0] if periodicos else "",
            )
        )
    log.info("  [Crossref] '%s': %s artigos", tema, len(artigos))
    return artigos


def _chave_deduplicacao(a: Dict) -> str:
    doi = _normalizar_doi(a.get("doi", ""))
    if doi:
        return f"doi:{doi}"
    titulo = re.sub(r"[^\w]", "", (a.get("titulo") or "").lower(), flags=re.UNICODE)
    return f"titulo:{titulo}"


def _mesclar_registros(base: Dict, novo: Dict) -> Dict:
    """Conserva o registro mais completo sem fabricar acesso aberto."""
    resultado = dict(base)
    for campo in ["abstract", "autores", "url_pdf", "url_texto_completo", "periodico"]:
        if len(str(novo.get(campo, ""))) > len(str(resultado.get(campo, ""))):
            resultado[campo] = novo.get(campo, "")
    resultado["cit_total"] = max(int(base.get("cit_total", 0)), int(novo.get("cit_total", 0)))
    resultado["cit_influ"] = max(int(base.get("cit_influ", 0)), int(novo.get("cit_influ", 0)))
    resultado["open_access"] = bool(resultado.get("url_pdf") or resultado.get("url_texto_completo"))
    resultado["tipos"] = sorted(set((base.get("tipos") or []) + (novo.get("tipos") or [])))
    fontes = set(base.get("fontes_encontradas") or [base.get("fonte")])
    fontes.add(novo.get("fonte"))
    resultado["fontes_encontradas"] = sorted(f for f in fontes if f)
    resultado["rank_fonte"] = min(int(base.get("rank_fonte", 999)), int(novo.get("rank_fonte", 999)))
    return resultado


def enriquecer_registros(base: List[Dict], extras: List[Dict]) -> List[Dict]:
    """Mescla metadados extras SOMENTE em artigos já descobertos.

    Registros exclusivos de Semantic Scholar/OpenAlex/Crossref são ignorados.
    Assim, uma base multidisciplinar nunca inclui sozinha um artigo na fila.
    """
    por_chave = {_chave_deduplicacao(a): dict(a) for a in base if _chave_deduplicacao(a)}
    for extra in extras:
        chave = _chave_deduplicacao(extra)
        if chave in por_chave:
            por_chave[chave] = _mesclar_registros(por_chave[chave], extra)
    return list(por_chave.values())


def _eh_tipo_editorial_excluido(tipos: List[str]) -> bool:
    tipos_set = set(tipos or [])
    excluidos = {"Editorial", "Opinion", "Letter", "Conference", "proceedings-article", "book-chapter"}
    return bool(tipos_set) and tipos_set.issubset(excluidos)


def deduplicar(artigos: List[Dict]) -> List[Dict]:
    por_chave: Dict[str, Dict] = {}
    for a in artigos:
        chave = _chave_deduplicacao(a)
        if not chave or chave.endswith(":"):
            continue
        if chave in por_chave:
            por_chave[chave] = _mesclar_registros(por_chave[chave], a)
        else:
            a = dict(a)
            a["fontes_encontradas"] = [a.get("fonte")]
            por_chave[chave] = a
    return list(por_chave.values())


def filtrar(artigos: List[Dict]) -> List[Dict]:
    """Seleciona TODOS os artigos elegíveis acima do limiar de prioridade.

    Não existe limite máximo de artigos selecionados por tema. O parâmetro
    O corte editorial é fixo em 60 pontos nesta etapa.
    """
    candidatos = []
    for a in artigos:
        if a.get("retracted"):
            continue
        if _eh_tipo_editorial_excluido(a.get("tipos") or []):
            continue
        abstract = (a.get("abstract") or "").strip()
        if len(abstract) < 100:
            continue
        metadados = calcular_prioridade_editorial(a)
        if metadados["score_prioridade_editorial"] < MIN_PRIORIDADE_EDITORIAL:
            continue
        candidatos.append(
            {
                "paper_id": a.get("paper_id", ""),
                "doi": a.get("doi", ""),
                "fonte_origem": a.get("fonte", ""),
                "fontes_encontradas": a.get("fontes_encontradas", []),
                "titulo": a.get("titulo", ""),
                "abstract": abstract,
                "ano": a.get("ano"),
                "autores": a.get("autores", ""),
                "periodico": a.get("periodico", ""),
                "citacoes_totais": a.get("cit_total", 0),
                "citacoes_influentes": a.get("cit_influ", 0),
                "tipos": a.get("tipos", []),
                "open_access": a.get("open_access", False),
                "url_pdf": a.get("url_pdf", ""),
                "url_texto_completo": a.get("url_texto_completo", ""),
                "url_artigo": a.get("url_artigo", ""),
                **metadados,
            }
        )
    candidatos.sort(key=lambda x: x["score_prioridade_editorial"], reverse=True)
    return candidatos


def coletar(temas: List[str], limite_busca: int, saida: str) -> Dict:
    log.info("Iniciando coleta biomédica federada | %s tema(s)", len(temas))
    resultado = {
        "gerado_em": datetime.now().isoformat(),
        "versao_pipeline": "4.2",
        "parametros": {
            "min_prioridade": MIN_PRIORIDADE_EDITORIAL,
            "limite_busca_por_fonte": limite_busca,
            "criterio_selecao": (
                "Todos os artigos elegíveis com score_prioridade_editorial maior ou igual "
                "ao limiar mínimo; não há máximo de selecionados por tema."
            ),
            "fontes_descoberta": ["PubMed", "Europe PMC", "Embase (quando autorizado)"],
            "fontes_enriquecimento": ["Semantic Scholar", "OpenAlex", "Crossref"],
            "embase": (
                "Fonte biomédica de descoberta habilitada quando EMBASE_API_KEY está configurada "
                "e a assinatura institucional possui entitlement para a Embase API. "
                "A chave nunca é gravada no arquivo de saída."
            ),
            "cochrane": (
                "Fonte especializada recomendada para consulta editorial/revisões, mas não "
                "integrada automaticamente nesta versão por não haver uma API pública aberta "
                "equivalente às fontes biomédicas usadas aqui."
            ),
            "score": (
                "prioridade editorial = desenho (0-50) + atualidade (0-20) + "
                "impacto bibliométrico logarítmico (0-20) + acesso (0-10) + "
                "relevância na fonte (0-10)"
            ),
            "aviso": (
                "O score é operacional e não substitui avaliação crítica da evidência, "
                "risco de viés, certeza da evidência ou adequação à pergunta clínica."
            ),
        },
        "temas": {},
        "total_artigos": 0,
    }

    for tema in temas:
        log.info("\nBuscando: '%s'", tema)
        limite = max(1, int(limite_busca))

        # 1) DESCOBERTA: somente fontes biomédicas/life sciences selecionadas.
        pubmed = buscar_pubmed(tema, limite)
        europe_pmc = buscar_europe_pmc(tema, limite)
        embase = buscar_embase(tema, limite)
        descobertos = deduplicar(pubmed + europe_pmc + embase)

        # Marca explicitamente em quais fontes biomédicas o artigo foi descoberto.
        for art in descobertos:
            art["fontes_descoberta"] = [
                f for f in (art.get("fontes_encontradas") or [art.get("fonte")])
                if f in {"PubMed", "EuropePMC", "Embase"}
            ]

        # 2) ENRIQUECIMENTO: bases multidisciplinares só completam registros existentes.
        cont_enriq = {"SemanticScholar": 0, "OpenAlex": 0, "Crossref": 0}
        pool = descobertos
        if ATIVAR_ENRIQUECIMENTO and descobertos:
            s2 = buscar_s2(tema, limite)
            oa = buscar_openalex(tema, limite)
            cr = buscar_crossref(tema, limite)
            cont_enriq = {
                "SemanticScholar": len(s2),
                "OpenAlex": len(oa),
                "Crossref": len(cr),
            }
            pool = enriquecer_registros(pool, s2)
            pool = enriquecer_registros(pool, oa)
            pool = enriquecer_registros(pool, cr)

        selecionados = filtrar(pool)
        for art in selecionados:
            # Não deixar a fonte multidisciplinar aparecer como origem de descoberta.
            descob = art.get("fontes_descoberta") or []
            if not descob:
                fontes = art.get("fontes_encontradas") or []
                descob = [f for f in fontes if f in {"PubMed", "EuropePMC", "Embase"}]
            art["fontes_descoberta"] = descob
            art["fonte_origem"] = (
                "PubMed" if "PubMed" in descob
                else ("Embase" if "Embase" in descob else ("EuropePMC" if "EuropePMC" in descob else art.get("fonte_origem", "")))
            )

        resultado["temas"][tema] = {
            "total_descobertos_biomedicos": len(descobertos),
            "total_selecionados": len(selecionados),
            "por_fonte_descoberta": {
                "PubMed": len(pubmed),
                "EuropePMC": len(europe_pmc),
                "Embase": len(embase),
            },
            "resultados_consultados_para_enriquecimento": cont_enriq,
            "artigos": selecionados,
        }
        resultado["total_artigos"] += len(selecionados)
        log.info(
            "  → %s selecionados de %s registros biomédicos únicos (PubMed:%s EuropePMC:%s Embase:%s)",
            len(selecionados), len(descobertos), len(pubmed), len(europe_pmc), len(embase)
        )
        time.sleep(0.8)

    with open(saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, indent=2, ensure_ascii=False)

    print("\n" + "=" * 72)
    print("  COLETA BIOMÉDICA CONCLUÍDA — Jornal Cienc.IA v4.3")
    print(f"  Temas: {len(temas)}")
    print(f"  Artigos selecionados: {resultado['total_artigos']}")
    print(f"  Prioridade editorial mínima fixa: {MIN_PRIORIDADE_EDITORIAL:.0f}")
    print("  Descoberta: PubMed + Europe PMC + Embase (quando autorizado)")
    print("  Enriquecimento: Semantic Scholar + OpenAlex + Crossref")
    print(f"  Saída: {saida}")
    print("=" * 72)
    return resultado


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta biomédica: PubMed + Europe PMC + Embase opcional; enriquecimento bibliográfico separado")
    parser.add_argument("--temas", nargs="+", default=TEMAS_PADRAO)
    parser.add_argument(
        "--limite-busca",
        type=int,
        default=200,
        help=(
            "Quantidade máxima de resultados consultados POR FONTE e POR TEMA antes da "
            "triagem. Não limita quantos artigos podem ser selecionados (padrão: 200)."
        ),
    )
    parser.add_argument("--saida", default="artigos_coletados.json")
    parser.add_argument(
        "--testar-embase",
        action="store_true",
        help="Faz uma consulta mínima para verificar API key/entitlement do Embase sem executar a coleta.",
    )
    args = parser.parse_args()
    if args.testar_embase:
        testar_acesso_embase()
    else:
        coletar(args.temas, args.limite_busca, args.saida)
