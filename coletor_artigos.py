# -*- coding: utf-8 -*-
"""
coletor_artigos.py — Busca federada e seleção de fontes científicas biomédicas
Jornal Cienc.IA · coletor biomédico · versão 5.1

O coletor usa somente PubMed, OpenAlex e, quando houver credenciais/entitlement, Embase
como fontes de descoberta. Semantic Scholar, Crossref e Europe PMC não são consultados.
Os resultados são deduplicados antes da triagem.

O coletor NÃO calcula nota numérica de qualidade ou prioridade. O fluxo é:

  1. busca por tema;
  2. deduplicação por DOI ou título;
  3. triagem objetiva de elegibilidade;
  4. priorização de revisões sistemáticas e meta-análises, quando disponíveis;
  5. demais estudos elegíveis em ordem de relevância retornada pelas bases;
  6. seleção de uma fila editorial manejável por tema.

A preferência por sínteses de evidência é uma regra de seleção editorial, não uma
avaliação automática da qualidade metodológica de cada estudo. O coletor não aplica
OCEBM nem JBI e não transforma desenho, citações, idade, acesso ou rank em uma nota.

Uso:
    python coletor_artigos.py
    python coletor_artigos.py --temas "diet liver disease" "vaccine safety"
    python coletor_artigos.py --limite-busca 200 --limite-selecionados 20
"""

from __future__ import annotations

import argparse
import json
import logging
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

EMBASE_API_KEY = os.getenv("EMBASE_API_KEY", "").strip()
EMBASE_INSTTOKEN = os.getenv("EMBASE_INSTTOKEN", "").strip()
ATIVAR_EMBASE = os.getenv("ATIVAR_EMBASE", "1").strip() != "0"
NCBI_KEY = os.getenv("NCBI_API_KEY", "")
EMAIL = os.getenv("USER_EMAIL", "contato@example.com")
ANO_ATUAL = datetime.now().year


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

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
OPENALEX_URL = "https://api.openalex.org/works"
EMBASE_URL = "https://api.elsevier.com/content/embase/article"


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


# Especificidade de metadados, NÃO hierarquia de evidência.
# Serve apenas para escolher um rótulo representativo quando a base informa vários tipos.
ORDEM_TIPO_ESPECIFICO = (
    "MetaAnalysis", "SystematicReview", "RCT", "ClinicalTrial", "CohortStudy",
    "CaseControlStudy", "ObservationalStudy", "CaseSeries", "CaseReport", "Review",
    "JournalArticle", "journal-article", "preprint", "Conference",
    "proceedings-article", "book-chapter", "Editorial", "Opinion", "Letter",
)


def classificar_desenho_metadados(tipos: List[str]) -> Tuple[str, str]:
    """Escolhe o tipo mais específico informado pelas bases, sem pontuar qualidade."""
    tipos = tipos or ["JournalArticle"]
    conjunto = set(tipos)
    principal = next((tipo for tipo in ORDEM_TIPO_ESPECIFICO if tipo in conjunto), tipos[0])
    return principal, ROTULO_DESENHO.get(principal, principal)


def avaliar_elegibilidade(a: Dict) -> Dict:
    """Aplica apenas critérios objetivos necessários para o artigo entrar na fila editorial."""
    tipos = a.get("tipos") or []
    abstract = (a.get("abstract") or "").strip()

    criterios = {
        "nao_retratado": not bool(a.get("retracted")),
        "tipo_publicacao_aceito": (
            not _eh_tipo_editorial_excluido(tipos)
            and not _eh_revisao_narrativa(tipos)
        ),
        # Critério operacional: o restante do pipeline trabalha a partir do resumo científico.
        "abstract_minimo_100_caracteres": len(abstract) >= 100,
    }

    motivos = []
    if not criterios["nao_retratado"]:
        motivos.append("registro retratado")
    if not criterios["tipo_publicacao_aceito"]:
        if _eh_revisao_narrativa(tipos):
            motivos.append("revisão narrativa/genérica sem identificação de revisão sistemática ou meta-análise")
        else:
            motivos.append("tipo de publicação não elegível")
    if not criterios["abstract_minimo_100_caracteres"]:
        motivos.append("resumo ausente ou insuficiente para o pipeline")

    return {
        "elegivel": all(criterios.values()),
        "criterios": criterios,
        "motivos_exclusao": motivos,
        "observacao": (
            "Triagem operacional de elegibilidade. Não representa nível de evidência "
            "nem avaliação automática da qualidade metodológica."
        ),
    }


def eh_sintese_evidencia(tipos: List[str]) -> bool:
    """Identifica revisões sistemáticas/meta-análises para prioridade editorial de leitura."""
    tipos_set = set(tipos or [])
    return bool(tipos_set & {"SystematicReview", "MetaAnalysis"})


def categoria_selecao(tipos: List[str]) -> Tuple[str, str]:
    if eh_sintese_evidencia(tipos):
        return "sintese_evidencia", "Revisão sistemática / meta-análise"
    return "estudo_elegivel", "Estudo científico elegível"


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


def _eh_tipo_editorial_excluido(tipos: List[str]) -> bool:
    tipos_set = set(tipos or [])
    excluidos = {"Editorial", "Opinion", "Letter", "Conference", "proceedings-article", "book-chapter", "preprint"}
    return bool(tipos_set) and tipos_set.issubset(excluidos)


def _eh_revisao_narrativa(tipos: List[str]) -> bool:
    """Exclui review genérico quando não há identificação de revisão sistemática/meta-análise."""
    tipos_set = set(tipos or [])
    return (
        "Review" in tipos_set
        and not bool(tipos_set & {"SystematicReview", "MetaAnalysis"})
    )


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


def selecionar_fontes(artigos: List[Dict], limite_selecionados: int) -> Tuple[List[Dict], int]:
    """Seleciona fontes sem criar escore numérico.

    Ordem editorial:
      1. relevância retornada pelas próprias bases de busca;
      2. em posições equivalentes, preferência por revisão sistemática/meta-análise;
      3. em novo empate, publicação mais recente.

    Revisões narrativas/genéricas são excluídas da fila porque não representam
    sínteses sistemáticas de evidência.

    ``limite_selecionados`` é somente um limite operacional da fila. Valor <= 0 mantém
    todos os elegíveis.
    """
    elegiveis = []

    for a in artigos:
        triagem = avaliar_elegibilidade(a)
        if not triagem["elegivel"]:
            continue

        principal, rotulo = classificar_desenho_metadados(a.get("tipos") or [])
        categoria, categoria_rotulo = categoria_selecao(a.get("tipos") or [])
        abstract = (a.get("abstract") or "").strip()
        rank = max(0, int(a.get("rank_fonte", 0) or 0))

        elegiveis.append({
            "paper_id": a.get("paper_id", ""),
            "doi": a.get("doi", ""),
            "fonte_origem": a.get("fonte", ""),
            "fontes_encontradas": a.get("fontes_encontradas", []),
            "titulo": a.get("titulo", ""),
            "abstract": abstract,
            "ano": a.get("ano"),
            "autores": a.get("autores", ""),
            "periodico": a.get("periodico", ""),
            # Metadados preservados para rastreabilidade; não entram em uma nota.
            "citacoes_totais": a.get("cit_total", 0),
            "citacoes_influentes": a.get("cit_influ", 0),
            "rank_fonte": rank,
            "tipos": a.get("tipos", []),
            "tipo_principal": principal,
            "desenho_estudo_rotulo": rotulo,
            "open_access": a.get("open_access", False),
            "url_pdf": a.get("url_pdf", ""),
            "url_texto_completo": a.get("url_texto_completo", ""),
            "url_artigo": a.get("url_artigo", ""),
            "triagem_elegibilidade": triagem,
            "categoria_selecao": categoria,
            "categoria_selecao_rotulo": categoria_rotulo,
            "criterio_selecao": (
                "Revisão sistemática/meta-análise elegível."
                if categoria == "sintese_evidencia"
                else "Estudo científico elegível; ordenado pela relevância retornada na busca."
            ),
        })

    total_elegiveis = len(elegiveis)

    elegiveis.sort(
        key=lambda x: (
            # A relevância calculada pela própria base é o critério principal.
            int(x.get("rank_fonte", 10**9) or 10**9),
            # Em posições equivalentes, sínteses sistemáticas recebem preferência.
            0 if x.get("categoria_selecao") == "sintese_evidencia" else 1,
            # Último desempate: artigo mais recente.
            -int(x.get("ano") or 0),
            str(x.get("titulo") or "").lower(),
        )
    )

    if int(limite_selecionados or 0) > 0:
        selecionados = elegiveis[: int(limite_selecionados)]
    else:
        selecionados = elegiveis

    for posicao, artigo in enumerate(selecionados, start=1):
        artigo["ordem_selecao"] = posicao

    return selecionados, total_elegiveis


def coletar(temas: List[str], limite_busca: int, limite_selecionados: int, saida: str) -> Dict:
    log.info("Iniciando coleta | %s tema(s) | fontes: PubMed + OpenAlex + Embase opcional", len(temas))
    resultado = {
        "gerado_em": datetime.now().isoformat(),
        "versao_pipeline": "5.1",
        "parametros": {
            "limite_busca_por_fonte": limite_busca,
            "criterio_selecao": (
                "Após a triagem objetiva, revisões sistemáticas e meta-análises são "
                "priorizadas; os demais estudos elegíveis seguem pela relevância da busca."
            ),
            "limite_selecionados_por_tema": limite_selecionados,
            "fontes_descoberta": ["PubMed", "OpenAlex", "Embase (quando autorizado)"],
            "fontes_removidas": ["Semantic Scholar", "Crossref", "Europe PMC"],
            "embase": (
                "Fonte habilitada quando EMBASE_API_KEY está configurada e a assinatura "
                "institucional possui entitlement para a Embase API. A chave nunca é gravada na saída."
            ),
            "triagem_elegibilidade": {
                "nao_retratado": True,
                "tipo_publicacao_aceito": True,
                "abstract_minimo": "100 caracteres (critério operacional de sanidade do pipeline)",
            },
            "selecao_editorial": {
                "regra": (
                    "1) sínteses de evidência elegíveis; 2) demais estudos elegíveis; "
                    "3) relevância retornada pelas bases dentro de cada grupo."
                ),
                "sem_escore_numerico": True,
                "observacao": (
                    "A regra organiza a fila de leitura e não equivale a uma avaliação "
                    "automática da qualidade metodológica do estudo."
                ),
                "referencia_conceitual": (
                    "OCEBM Levels of Evidence Working Group (2011): busca da provável "
                    "melhor evidência e preferência por sínteses sistemáticas quando apropriado."
                ),
            },
        },
        "temas": {},
        "total_artigos": 0,
    }

    for tema in temas:
        log.info("\nBuscando: '%s'", tema)
        termos_tema = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", str(tema or ""))
        if len(termos_tema) <= 1:
            log.warning(
                "  Tema muito amplo ('%s'). A busca continuará, mas consultas com mais contexto "
                "tendem a retornar fontes mais específicas (ex.: população + exposição/intervenção + desfecho).",
                tema,
            )
        limite = max(1, int(limite_busca))

        pubmed = buscar_pubmed(tema, limite)
        openalex = buscar_openalex(tema, limite)
        embase = buscar_embase(tema, limite)

        descobertos = deduplicar(pubmed + openalex + embase)
        fontes_validas = {"PubMed", "OpenAlex", "Embase"}
        for art in descobertos:
            fontes = art.get("fontes_encontradas") or [art.get("fonte")]
            art["fontes_descoberta"] = [f for f in fontes if f in fontes_validas]

        selecionados, total_elegiveis = selecionar_fontes(descobertos, limite_selecionados)
        for art in selecionados:
            descob = art.get("fontes_descoberta") or []
            if not descob:
                fontes = art.get("fontes_encontradas") or []
                descob = [f for f in fontes if f in fontes_validas]
            art["fontes_descoberta"] = descob
            art["fonte_origem"] = (
                "PubMed" if "PubMed" in descob
                else ("Embase" if "Embase" in descob
                      else ("OpenAlex" if "OpenAlex" in descob else art.get("fonte_origem", "")))
            )

        resultado["temas"][tema] = {
            "total_descobertos": len(descobertos),
            "total_elegiveis": total_elegiveis,
            "total_selecionados": len(selecionados),
            "por_fonte_descoberta": {
                "PubMed": len(pubmed),
                "OpenAlex": len(openalex),
                "Embase": len(embase),
            },
            "artigos": selecionados,
        }
        resultado["total_artigos"] += len(selecionados)
        log.info(
            "  → %s elegíveis; %s selecionados de %s registros únicos (PubMed:%s OpenAlex:%s Embase:%s)",
            total_elegiveis, len(selecionados), len(descobertos), len(pubmed), len(openalex), len(embase)
        )
        time.sleep(0.8)

    with open(saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, indent=2, ensure_ascii=False)

    print("\n" + "=" * 72)
    print("  COLETA CONCLUÍDA — Jornal Cienc.IA v5.1")
    print(f"  Temas: {len(temas)}")
    print(f"  Artigos selecionados para a fila: {resultado['total_artigos']}")
    print(f"  Limite operacional por tema: {limite_selecionados if limite_selecionados > 0 else 'todos os elegíveis'}")
    print("  Seleção: sínteses de evidência primeiro; depois demais elegíveis por relevância")
    print("  Sem nota numérica de prioridade ou qualidade")
    print("  Fontes: PubMed + OpenAlex + Embase (quando autorizado)")
    print("  Semantic Scholar, Crossref e Europe PMC: não consultados")
    print(f"  Saída: {saida}")
    print("=" * 72)
    return resultado


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta de artigos: PubMed + OpenAlex + Embase opcional")
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
    parser.add_argument(
        "--limite-selecionados",
        type=int,
        default=20,
        help=(
            "Quantidade máxima de fontes enviadas à fila editorial POR TEMA após a triagem "
            "(padrão: 20). Use 0 para manter todos os elegíveis."
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
        coletar(args.temas, args.limite_busca, args.limite_selecionados, args.saida)
