# medir_bertscore_tcc.py
#
# Compara, para TODOS os artigos do noticias.json:
#   referência = resumo_cientifico_traduzido
#   candidato 1 = divulgacao_cientifica      (Nível 1)
#   candidato 2 = leitura_facilitada         (Nível 2)
#
# Saídas:
#   - bertscore_resultados.csv
#   - bertscore_resumo.json
#
# Instalação:
#   pip install bert-score pandas torch
#
# Execução:
#   python medir_bertscore_tcc.py noticias.json
#
# Observação:
# BERTScore mede preservação/semelhança semântica, NÃO comprova factualidade.

import argparse
import json
import re
from pathlib import Path

import pandas as pd
import torch
from bert_score import BERTScorer


# Modelo multilíngue explicitado para reprodutibilidade.
# É o modelo padrão usado pelo BERTScore para idiomas não ingleses.
MODEL_TYPE = "bert-base-multilingual-cased"

# Textos muito longos podem ultrapassar o limite de contexto do encoder.
# O script não exclui nenhum artigo, mas marca os casos para revisão.
LONG_TEXT_WORD_WARNING = 450


def limpar_texto(texto):
    """Normaliza espaços sem alterar o conteúdo."""
    if texto is None:
        return ""
    texto = str(texto).strip()
    return re.sub(r"\s+", " ", texto)


def contar_palavras(texto):
    return len(limpar_texto(texto).split())


def media(lista):
    return sum(lista) / len(lista) if lista else 0.0


def desvio_padrao(lista):
    if len(lista) < 2:
        return 0.0
    m = media(lista)
    return (sum((x - m) ** 2 for x in lista) / (len(lista) - 1)) ** 0.5


def carregar_artigos(caminho):
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    if not isinstance(dados, list):
        raise ValueError(
            "O JSON deveria ter uma lista de artigos no nível principal."
        )

    return dados


def preparar_pares(artigos):
    """
    Retorna apenas artigos que possuam os três textos necessários.
    Não filtra por status editorial, fidelidade ou publicação.
    """
    linhas = []

    for indice, artigo in enumerate(artigos, start=1):
        referencia = limpar_texto(
            artigo.get("resumo_cientifico_traduzido")
            or artigo.get("texto_fonte_pt")
            or artigo.get("abstract_pt")
        )

        nivel_1 = limpar_texto(
            artigo.get("divulgacao_cientifica")
            or artigo.get("leve")
        )

        nivel_2 = limpar_texto(
            artigo.get("leitura_facilitada")
            or artigo.get("forte")
        )

        if not referencia or not nivel_1 or not nivel_2:
            print(
                f"[AVISO] Artigo {indice} ignorado: "
                "faltou referência, Nível 1 ou Nível 2."
            )
            continue

        palavras_ref = contar_palavras(referencia)
        palavras_n1 = contar_palavras(nivel_1)
        palavras_n2 = contar_palavras(nivel_2)

        linhas.append(
            {
                "indice_json": indice,
                "paper_id": artigo.get("paper_id", ""),
                "doi": artigo.get("doi", ""),
                "tema": artigo.get("tema_exibicao") or artigo.get("tema") or "",
                "titulo": (
                    artigo.get("titulo_pt")
                    or artigo.get("titulo_original")
                    or artigo.get("manchete")
                    or f"Artigo {indice}"
                ),
                "referencia": referencia,
                "nivel_1": nivel_1,
                "nivel_2": nivel_2,
                "palavras_referencia": palavras_ref,
                "palavras_n1": palavras_n1,
                "palavras_n2": palavras_n2,
                "alerta_texto_longo": (
                    palavras_ref > LONG_TEXT_WORD_WARNING
                    or palavras_n1 > LONG_TEXT_WORD_WARNING
                    or palavras_n2 > LONG_TEXT_WORD_WARNING
                ),
            }
        )

    return linhas


def tensor_para_lista(tensor):
    return tensor.detach().cpu().tolist()


def calcular_bertscore(linhas):
    if not linhas:
        raise ValueError("Nenhum artigo válido foi encontrado.")

    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"\nDispositivo: {device}")
    print(f"Modelo: {MODEL_TYPE}")
    print(f"Artigos avaliados: {len(linhas)}")

    # BERTScorer mantém o modelo carregado e o reutiliza.
    scorer = BERTScorer(
        model_type=MODEL_TYPE,
        lang="pt",
        device=device,
        idf=False,
        rescale_with_baseline=False,
    )

    referencias = [x["referencia"] for x in linhas]
    candidatos_n1 = [x["nivel_1"] for x in linhas]
    candidatos_n2 = [x["nivel_2"] for x in linhas]

    print("\nCalculando BERTScore do Nível 1...")
    p1, r1, f1_1 = scorer.score(
        candidatos_n1,
        referencias,
        batch_size=4 if device == "cuda" else 1,
    )

    print("Calculando BERTScore do Nível 2...")
    p2, r2, f1_2 = scorer.score(
        candidatos_n2,
        referencias,
        batch_size=4 if device == "cuda" else 1,
    )

    p1 = tensor_para_lista(p1)
    r1 = tensor_para_lista(r1)
    f1_1 = tensor_para_lista(f1_1)

    p2 = tensor_para_lista(p2)
    r2 = tensor_para_lista(r2)
    f1_2 = tensor_para_lista(f1_2)

    resultados = []

    for i, linha in enumerate(linhas):
        resultados.append(
            {
                "indice_json": linha["indice_json"],
                "paper_id": linha["paper_id"],
                "doi": linha["doi"],
                "tema": linha["tema"],
                "titulo": linha["titulo"],

                "palavras_referencia": linha["palavras_referencia"],
                "palavras_n1": linha["palavras_n1"],
                "palavras_n2": linha["palavras_n2"],
                "alerta_texto_longo": linha["alerta_texto_longo"],

                "bertscore_precision_n1": round(float(p1[i]), 6),
                "bertscore_recall_n1": round(float(r1[i]), 6),
                "bertscore_f1_n1": round(float(f1_1[i]), 6),

                "bertscore_precision_n2": round(float(p2[i]), 6),
                "bertscore_recall_n2": round(float(r2[i]), 6),
                "bertscore_f1_n2": round(float(f1_2[i]), 6),

                # Positivo = N2 teve F1 maior que N1.
                "delta_f1_n2_menos_n1": round(
                    float(f1_2[i] - f1_1[i]), 6
                ),
            }
        )

    return resultados, scorer


def montar_resumo(resultados, scorer):
    def coluna(nome):
        return [float(x[nome]) for x in resultados]

    p1 = coluna("bertscore_precision_n1")
    r1 = coluna("bertscore_recall_n1")
    f1_n1 = coluna("bertscore_f1_n1")

    p2 = coluna("bertscore_precision_n2")
    r2 = coluna("bertscore_recall_n2")
    f1_n2 = coluna("bertscore_f1_n2")

    longos = sum(bool(x["alerta_texto_longo"]) for x in resultados)

    resumo = {
        "n_artigos": len(resultados),
        "modelo": MODEL_TYPE,
        "idioma": "pt",
        "idf": False,
        "rescale_with_baseline": False,
        "hash_configuracao_bertscore": scorer.hash,
        "referencia": "resumo_cientifico_traduzido; fallback texto_fonte_pt/abstract_pt",
        "nivel_1": "divulgacao_cientifica",
        "nivel_2": "leitura_facilitada",
        "observacao": (
            "BERTScore mede preservação/semelhança semântica. "
            "Não deve ser interpretado isoladamente como medida de factualidade."
        ),
        "textos_com_alerta_de_comprimento": longos,
        "nivel_1_resultados": {
            "precision_media": round(media(p1), 6),
            "precision_dp": round(desvio_padrao(p1), 6),
            "recall_media": round(media(r1), 6),
            "recall_dp": round(desvio_padrao(r1), 6),
            "f1_media": round(media(f1_n1), 6),
            "f1_dp": round(desvio_padrao(f1_n1), 6),
            "f1_min": round(min(f1_n1), 6),
            "f1_max": round(max(f1_n1), 6),
        },
        "nivel_2_resultados": {
            "precision_media": round(media(p2), 6),
            "precision_dp": round(desvio_padrao(p2), 6),
            "recall_media": round(media(r2), 6),
            "recall_dp": round(desvio_padrao(r2), 6),
            "f1_media": round(media(f1_n2), 6),
            "f1_dp": round(desvio_padrao(f1_n2), 6),
            "f1_min": round(min(f1_n2), 6),
            "f1_max": round(max(f1_n2), 6),
        },
        "comparacao_n2_vs_n1": {
            "delta_medio_f1": round(
                media([b - a for a, b in zip(f1_n1, f1_n2)]), 6
            ),
            "n_n2_maior_que_n1": sum(
                b > a for a, b in zip(f1_n1, f1_n2)
            ),
            "n_n1_maior_que_n2": sum(
                a > b for a, b in zip(f1_n1, f1_n2)
            ),
            "n_empates": sum(
                abs(a - b) < 1e-12 for a, b in zip(f1_n1, f1_n2)
            ),
        },
    }

    return resumo


def imprimir_resumo(resumo):
    n1 = resumo["nivel_1_resultados"]
    n2 = resumo["nivel_2_resultados"]
    comp = resumo["comparacao_n2_vs_n1"]

    print("\n" + "=" * 72)
    print("RESUMO BERTSCORE")
    print("=" * 72)
    print(f"Artigos avaliados: {resumo['n_artigos']}")
    print(f"Modelo: {resumo['modelo']}")
    print(f"Hash BERTScore: {resumo['hash_configuracao_bertscore']}")
    print()

    print("NÍVEL 1 — DIVULGAÇÃO CIENTÍFICA")
    print(
        f"P = {n1['precision_media']:.4f} ± {n1['precision_dp']:.4f}"
    )
    print(
        f"R = {n1['recall_media']:.4f} ± {n1['recall_dp']:.4f}"
    )
    print(
        f"F1 = {n1['f1_media']:.4f} ± {n1['f1_dp']:.4f}"
    )

    print("\nNÍVEL 2 — LEITURA FACILITADA")
    print(
        f"P = {n2['precision_media']:.4f} ± {n2['precision_dp']:.4f}"
    )
    print(
        f"R = {n2['recall_media']:.4f} ± {n2['recall_dp']:.4f}"
    )
    print(
        f"F1 = {n2['f1_media']:.4f} ± {n2['f1_dp']:.4f}"
    )

    print("\nCOMPARAÇÃO")
    print(f"Δ F1 médio (N2 - N1): {comp['delta_medio_f1']:+.4f}")
    print(
        f"N2 > N1: {comp['n_n2_maior_que_n1']} | "
        f"N1 > N2: {comp['n_n1_maior_que_n2']} | "
        f"empates: {comp['n_empates']}"
    )

    if resumo["textos_com_alerta_de_comprimento"]:
        print(
            "\nATENÇÃO: "
            f"{resumo['textos_com_alerta_de_comprimento']} artigo(s) "
            f"têm algum texto acima de {LONG_TEXT_WORD_WARNING} palavras. "
            "Confira a coluna 'alerta_texto_longo', pois modelos BERT têm "
            "limite de contexto e textos muito longos podem ser truncados."
        )

    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(
        description="Calcula BERTScore dos níveis de simplificação do TCC."
    )
    parser.add_argument(
        "json",
        nargs="?",
        default="noticias.json",
        help="Caminho para o arquivo JSON. Padrão: noticias.json",
    )
    parser.add_argument(
        "--saida-csv",
        default="bertscore_resultados.csv",
        help="CSV com o resultado por artigo.",
    )
    parser.add_argument(
        "--saida-resumo",
        default="bertscore_resumo.json",
        help="JSON com médias e resumo geral.",
    )
    args = parser.parse_args()

    artigos = carregar_artigos(args.json)
    linhas = preparar_pares(artigos)

    print(
        f"JSON contém {len(artigos)} artigos; "
        f"{len(linhas)} possuem os textos necessários."
    )

    resultados, scorer = calcular_bertscore(linhas)
    resumo = montar_resumo(resultados, scorer)

    df = pd.DataFrame(resultados)
    df.to_csv(args.saida_csv, index=False, encoding="utf-8-sig")

    with open(args.saida_resumo, "w", encoding="utf-8") as f:
        json.dump(resumo, f, ensure_ascii=False, indent=2)

    imprimir_resumo(resumo)

    print(f"\nCSV salvo em: {Path(args.saida_csv).resolve()}")
    print(f"Resumo salvo em: {Path(args.saida_resumo).resolve()}")


if __name__ == "__main__":
    main()
