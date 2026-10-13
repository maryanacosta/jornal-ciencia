#!/usr/bin/env python3
"""Gera MP3s dos cards já publicados no Jornal Cienc.IA.

Coloque este arquivo ao lado de noticias.json e execute:
    python -m pip install edge-tts
    python gerar_audios.py --limitar 1
    python gerar_audios.py

Sem serviços pagos/chaves de API; a geração exige internet e pode deixar de
funcionar se o provedor mudar seu serviço. As notícias não são modificadas.
"""

import argparse
import asyncio
import hashlib
import json
import re
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TITULOS = [
    ("O principal", ("o_principal", "O principal", "principal")),
    ("O que o artigo fez", ("o_que_o_artigo_fez", "O que o artigo fez", "metodo")),
    ("O que foi encontrado", ("o_que_foi_encontrado", "O que foi encontrado", "resultados")),
    ("O que ainda não sabemos", ("o_que_ainda_nao_sabemos", "O que ainda não sabemos", "limitacoes")),
]


def texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def limpar_texto(valor):
    """Acompanha limparTexto() do artigo.js, sem mudar o conteúdo científico."""
    valor = texto(valor).replace('\\n', '\n').replace('\r', '').replace('\t', ' ').replace('**', '')
    valor = re.sub(r'^[\'"`]|[\'"`]$', '', valor)
    valor = re.sub(r'[ \t]+\n', '\n', valor)
    return re.sub(r'\n{3,}', '\n\n', valor).strip()


def primeira(objeto, alternativas):
    if not isinstance(objeto, dict):
        return ''
    for nome in alternativas:
        if texto(objeto.get(nome)):
            return limpar_texto(objeto[nome])
    return ''


def parse_objeto(valor):
    if isinstance(valor, dict):
        return valor
    if not isinstance(valor, str):
        return None
    bruto = limpar_texto(valor)
    if not bruto.startswith('{'):
        return None
    try:
        dados = json.loads(bruto)
        return dados if isinstance(dados, dict) else None
    except json.JSONDecodeError:
        try:
            ajustado = re.sub(r"([{,]\s*)'([^']+?)'\s*:", r'\1"\2":', bruto)
            ajustado = re.sub(r":\s*'([^']*?)'(\s*[,}])", r': "\1"\2', ajustado)
            dados = json.loads(ajustado)
            return dados if isinstance(dados, dict) else None
        except json.JSONDecodeError:
            return None


def blocos_facilitada(noticia):
    """Segue extrairLeituraFacilitada() do artigo.js, inclusive campos antigos."""
    objeto = noticia.get('leitura_facilitada_blocos')
    if not isinstance(objeto, dict):
        objeto = parse_objeto(noticia.get('forte') or noticia.get('leitura_facilitada'))
    if objeto is not None:
        return [(titulo, primeira(objeto, chaves)) for titulo, chaves in TITULOS if primeira(objeto, chaves)]

    bruto = limpar_texto(noticia.get('leitura_facilitada') or noticia.get('forte') or '')
    padrao = re.compile('(' + '|'.join(re.escape(titulo) for titulo, _ in TITULOS) + r')\s*[:\-]?', re.I)
    encontrados = list(padrao.finditer(bruto))
    if not encontrados:
        return [('O principal', bruto)] if bruto else []
    resultado = []
    for indice, encontrado in enumerate(encontrados):
        fim = encontrados[indice + 1].start() if indice + 1 < len(encontrados) else len(bruto)
        conteudo = bruto[encontrado.end():fim].strip()
        if conteudo:
            resultado.append((encontrado.group(1), conteudo))
    return resultado


def blocos_divulgacao(noticia):
    """Só cria MP3 para cards reais, não para textos legados fora de cards."""
    bruto = noticia.get('divulgacao_cientifica_blocos')
    if noticia.get('divulgacao_blocos_semanticos') is not True or not isinstance(bruto, list):
        return []
    resultado = []
    for item in bruto:
        if not isinstance(item, dict):
            continue
        titulo = limpar_texto(item.get('titulo') or item.get('rotulo') or item.get('nome') or '') or 'Conteúdo'
        conteudo = limpar_texto(item.get('texto') or item.get('conteudo') or item.get('valor') or '')
        if conteudo:
            resultado.append((titulo, conteudo))
    return resultado


def texto_visivel_no_card(valor):
    """Replica textoParaHtmlParagrafos() + textContent dos <p> no navegador.

    Quando há uma quebra de linha simples, o artigo.js usa <br> (não
    introduz espaço em textContent). Quebras duplas separam parágrafos.
    """
    limpo = limpar_texto(valor)
    if not limpo:
        return ''
    paragrafos = [p.strip() for p in re.split(r'\n\s*\n', limpo) if p.strip()]
    textos = [re.sub(r'\s+', ' ', p.replace('\n', '')).strip() for p in paragrafos]
    return ' '.join(p for p in textos if p)


def lista_cards(noticia):
    cards = []
    for prefixo, blocos in [('divulgacao', blocos_divulgacao(noticia)), ('facilitada', blocos_facilitada(noticia))]:
        for indice, (_, conteudo) in enumerate(blocos, start=1):
            tts_texto = texto_visivel_no_card(conteudo)
            if tts_texto:
                cards.append((f'{prefixo}-{indice}', tts_texto))
    return cards


async def gerar(arquivo_json, pasta, voz, ritmo, limitar, simular):
    if not arquivo_json.is_file():
        raise SystemExit(f'Arquivo não encontrado: {arquivo_json}\nColoque gerar_audios.py na pasta do site, junto ao noticias.json.')
    with arquivo_json.open(encoding='utf-8-sig') as arquivo:
        noticias = json.load(arquivo)
    if not isinstance(noticias, list):
        raise SystemExit('noticias.json deve conter uma lista de notícias.')
    conteudo = [(texto(n.get('paper_id')), lista_cards(n)) for n in noticias if isinstance(n, dict) and texto(n.get('paper_id'))]
    if limitar is not None:
        conteudo = conteudo[:limitar]

    total = sum(len(cards) for _, cards in conteudo)
    print(f'Artigos selecionados: {len(conteudo)} | cards com texto: {total}')
    if simular:
        for paper_id, cards in conteudo[:6]:
            print(f'  {paper_id[:70]}: {len(cards)} card(s) -> {", ".join(chave for chave, _ in cards)}')
        print('Simulação concluída; nenhum MP3 foi gerado.')
        return

    try:
        import edge_tts
    except ImportError as exc:
        raise SystemExit('Instale primeiro: python -m pip install edge-tts') from exc

    pasta.mkdir(parents=True, exist_ok=True)
    manifesto_path = pasta / 'manifesto.json'
    try:
        antigo = json.loads(manifesto_path.read_text(encoding='utf-8')) if manifesto_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        antigo = {}
    artigos_antigos = antigo.get('artigos', {}) if isinstance(antigo, dict) else {}
    if not isinstance(artigos_antigos, dict):
        artigos_antigos = {}
    artigos_novos = dict(artigos_antigos) if limitar is not None else {}
    gerados, reutilizados, erros = 0, 0, 0

    for posicao, (paper_id, cards) in enumerate(conteudo, start=1):
        hash_artigo = hashlib.sha256(paper_id.encode('utf-8')).hexdigest()[:16]
        destino_artigo = pasta / hash_artigo
        grupo = {}
        for chave, frase in cards:
            arquivo_relativo = f'audios/{hash_artigo}/{chave}.mp3'
            saida = destino_artigo / f'{chave}.mp3'
            referencia_antiga = artigos_antigos.get(paper_id, {}).get(chave, {})
            if (
                isinstance(referencia_antiga, dict)
                and referencia_antiga.get('texto') == frase
                and referencia_antiga.get('voz') == voz
                and referencia_antiga.get('ritmo') == ritmo
                and saida.is_file() and saida.stat().st_size > 0
            ):
                reutilizados += 1
                grupo[chave] = referencia_antiga
                continue

            destino_artigo.mkdir(parents=True, exist_ok=True)
            temp = saida.with_suffix('.tmp.mp3')
            sucesso = False
            for tentativa in range(2):
                try:
                    await edge_tts.Communicate(frase, voice=voz, rate=ritmo).save(str(temp))
                    if not temp.exists() or temp.stat().st_size < 100:
                        raise RuntimeError('O arquivo MP3 produzido está vazio/incompleto.')
                    os.replace(temp, saida)
                    sucesso = True
                    break
                except Exception as exc:
                    temp.unlink(missing_ok=True)
                    if tentativa == 0:
                        await asyncio.sleep(2)
                    else:
                        print(f'  ERRO em {paper_id[:32]} / {chave}: {exc}')
            if sucesso:
                gerados += 1
                grupo[chave] = {'arquivo': arquivo_relativo, 'texto': frase, 'voz': voz, 'ritmo': ritmo}
                print(f'  [{posicao}/{len(conteudo)}] MP3 criado: {chave}')
            else:
                erros += 1
                # Uma gravação antiga com a mesma frase ainda é válida.
                if (
                    isinstance(referencia_antiga, dict)
                    and referencia_antiga.get('texto') == frase
                    and saida.is_file() and saida.stat().st_size > 0
                ):
                    grupo[chave] = referencia_antiga
        if grupo:
            artigos_novos[paper_id] = grupo
        else:
            artigos_novos.pop(paper_id, None)

    manifesto = {'versao': 1, 'artigos': artigos_novos}
    rascunho = manifesto_path.with_suffix('.tmp.json')
    rascunho.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(rascunho, manifesto_path)
    print(f'\nConcluído: {gerados} novos, {reutilizados} reutilizados, {erros} falhas.')
    print(f'Manifesto salvo em: {manifesto_path}')
    if erros:
        print('Os cards sem MP3 válido continuarão usando a voz do navegador.')


def main():
    parser = argparse.ArgumentParser(description='Gera MP3s dos cards do Jornal Cienc.IA.')
    parser.add_argument('--noticias', type=Path, default=ROOT / 'noticias.json')
    parser.add_argument('--voz', default='pt-BR-FranciscaNeural')
    parser.add_argument('--ritmo', default='-5%')
    parser.add_argument('--limitar', type=int, default=None, help='Quantidade de artigos para testar primeiro.')
    parser.add_argument('--simular', action='store_true', help='Mostra o que será gerado sem instalar edge-tts.')
    args = parser.parse_args()
    asyncio.run(gerar(args.noticias, ROOT / 'audios', args.voz, args.ritmo, args.limitar, args.simular))


if __name__ == '__main__':
    main()
