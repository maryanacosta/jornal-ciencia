const TEMAS_PT = {
  diet: 'Dieta',
  sleep: 'Sono',
  nutrition: 'Nutrição',
  health: 'Saúde',
  'physical activity': 'Atividade física',
  sunscreen: 'Protetor solar',
  'sunscreen skin cancer prevention': 'Protetor solar e prevenção do câncer de pele',
  'cancer alternative medicine treatment': 'Câncer e tratamentos alternativos',
  'nutrition diet health outcomes': 'Alimentação, dieta e saúde',
  'influenza transmission cold weather': 'Influenza, transmissão e clima frio',
  'red meat processed food cancer risk': 'Carne vermelha, processados e risco de câncer',
  'vaccine safety adverse effects': 'Segurança de vacinas e efeitos adversos',
  'sugar consumption mental health anxiety': 'Consumo de açúcar, saúde mental e ansiedade',
  'ivermectin antiparasitic clinical use': 'Ivermectina e uso clínico antiparasitário',
  'egg cholesterol cardiovascular disease': 'Ovos, colesterol e doença cardiovascular',
  'detox diet liver kidney health': 'Dietas detox, fígado e rins'
};

let falaAtiva = null;
let botaoAudioAtivo = null;

function texto(valor) {
  return valor === undefined || valor === null ? '' : String(valor).trim();
}

function limparTexto(valor) {
  return texto(valor)
    .replace(/\\n/g, '\n')
    .replace(/\r/g, '')
    .replace(/\t/g, ' ')
    .replace(/\*\*/g, '')
    .replace(/^['"`]|['"`]$/g, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function escaparHtml(valor) {
  return limparTexto(valor)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatarTema(valor) {
  const chave = texto(valor).toLowerCase().replace(/_/g, ' ').trim();
  if (!chave) return 'Geral';
  return TEMAS_PT[chave] || chave.charAt(0).toUpperCase() + chave.slice(1);
}

function tituloNoticia(noticia) {
  return texto(noticia.manchete || noticia.titulo_pt || noticia.titulo_original || 'Sem título');
}

function tipoPrincipal(noticia) {
  const tipos = Array.isArray(noticia.tipos) ? noticia.tipos : [];
  return tipos[0] || noticia.desenho_estudo_rotulo || 'Artigo científico';
}

function valorPrimeiro(objeto, chaves) {
  for (const chave of chaves) {
    if (objeto && objeto[chave] !== undefined && objeto[chave] !== null && texto(objeto[chave])) {
      return limparTexto(objeto[chave]);
    }
  }
  return '';
}

function paragrafos(textoBruto) {
  const limpo = limparTexto(textoBruto);
  if (!limpo) return [];
  return limpo.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
}

function textoParaHtmlParagrafos(valor) {
  const ps = paragrafos(valor);
  if (!ps.length) return '<p>Informação não disponível.</p>';
  return ps.map(p => `<p>${escaparHtml(p).replace(/\n/g, '<br>')}</p>`).join('');
}

function normalizarBlocosPublicados(valor) {
  if (!Array.isArray(valor)) return [];
  return valor.map(item => {
    if (!item || typeof item !== 'object') return null;
    const titulo = limparTexto(item.titulo || item.rotulo || item.nome || '');
    const conteudo = limparTexto(item.texto || item.conteudo || item.valor || '');
    return conteudo ? { titulo: titulo || 'Conteúdo', texto: conteudo } : null;
  }).filter(Boolean);
}

function estruturarDivulgacao(textoBruto) {
  const limpo = limparTexto(textoBruto);
  if (!limpo) return [];

  // Compatibilidade segura para publicações antigas: não tentamos adivinhar
  // o significado de cada parágrafo pela posição. Sem blocos semânticos
  // confirmados, a divulgação aparece como um único texto.
  return [{ titulo: 'Divulgação científica', texto: limpo }];
}

function tentarParseObjeto(valor) {
  if (valor && typeof valor === 'object') return valor;
  const bruto = limparTexto(valor);
  if (!bruto || !bruto.startsWith('{')) return null;
  try {
    return JSON.parse(bruto);
  } catch (_) {
    try {
      const ajustado = bruto
        .replace(/([{,]\s*)'([^']+?)'\s*:/g, '$1"$2":')
        .replace(/:\s*'([^']*?)'(\s*[,}])/g, ': "$1"$2');
      return JSON.parse(ajustado);
    } catch (_) {
      return null;
    }
  }
}

function extrairLeituraFacilitada(noticia) {
  const blocos = noticia.leitura_facilitada_blocos;
  if (blocos && !Array.isArray(blocos) && typeof blocos === 'object') {
    return [
      { titulo: 'O principal', texto: valorPrimeiro(blocos, ['o_principal', 'O principal', 'principal']) },
      { titulo: 'O que o artigo fez', texto: valorPrimeiro(blocos, ['o_que_o_artigo_fez', 'O que o artigo fez', 'metodo']) },
      { titulo: 'O que foi encontrado', texto: valorPrimeiro(blocos, ['o_que_foi_encontrado', 'O que foi encontrado', 'resultados']) },
      { titulo: 'O que ainda não sabemos', texto: valorPrimeiro(blocos, ['o_que_ainda_nao_sabemos', 'O que ainda não sabemos', 'limitacoes']) }
    ].filter(bloco => bloco.texto);
  }

  const objeto = tentarParseObjeto(noticia.forte || noticia.leitura_facilitada);
  if (objeto) {
    return [
      { titulo: 'O principal', texto: valorPrimeiro(objeto, ['o_principal', 'O principal', 'principal']) },
      { titulo: 'O que o artigo fez', texto: valorPrimeiro(objeto, ['o_que_o_artigo_fez', 'O que o artigo fez', 'metodo']) },
      { titulo: 'O que foi encontrado', texto: valorPrimeiro(objeto, ['o_que_foi_encontrado', 'O que foi encontrado', 'resultados']) },
      { titulo: 'O que ainda não sabemos', texto: valorPrimeiro(objeto, ['o_que_ainda_nao_sabemos', 'O que ainda não sabemos', 'limitacoes']) }
    ].filter(bloco => bloco.texto);
  }

  const limpo = limparTexto(noticia.leitura_facilitada || noticia.forte || '');
  const titulos = [
    ['O principal', 'o_principal'],
    ['O que o artigo fez', 'o_que_o_artigo_fez'],
    ['O que foi encontrado', 'o_que_foi_encontrado'],
    ['O que ainda não sabemos', 'o_que_ainda_nao_sabemos']
  ];

  const padrao = new RegExp(`(${titulos.map(([t]) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\s*[:\\-]?`, 'gi');
  const encontrados = [];
  let match;
  while ((match = padrao.exec(limpo)) !== null) {
    encontrados.push({ titulo: match[1], inicio: match.index, conteudoInicio: padrao.lastIndex });
  }

  if (!encontrados.length) {
    return limpo ? [{ titulo: 'O principal', texto: limpo }] : [];
  }

  return encontrados.map((item, i) => {
    const fim = i + 1 < encontrados.length ? encontrados[i + 1].inicio : limpo.length;
    return { titulo: item.titulo, texto: limpo.slice(item.conteudoInicio, fim).trim() };
  }).filter(bloco => bloco.texto);
}

function obterResumoCientifico(noticia) {
  return limparTexto(
    noticia.resumo_cientifico_traduzido ||
    noticia.abstract_pt ||
    noticia.texto_fonte_pt ||
    ''
  );
}

function textoUnicoHtml(textoBruto, classeExtra = '') {
  const conteudo = limparTexto(textoBruto);
  return `
    <article class="single-text-card ${classeExtra}">
      ${conteudo ? textoParaHtmlParagrafos(conteudo) : '<p>Informação não disponível.</p>'}
    </article>
  `;
}

function cardsHtml(blocos, prefixo) {
  if (!blocos.length) {
    return '<article class="content-card"><div class="content-heading"><span class="content-number">01</span><h2>Conteúdo</h2></div><p>Informação não disponível.</p></article>';
  }

  return blocos.map((bloco, indice) => `
    <article class="content-card" id="${prefixo}-${indice + 1}">
      <div class="content-heading">
        <span class="content-number">${String(indice + 1).padStart(2, '0')}</span>
        <h2>${escaparHtml(bloco.titulo || 'Conteúdo')}</h2>
      </div>
      ${textoParaHtmlParagrafos(bloco.texto)}
    </article>`).join('');
}

function urlFonteOriginal(noticia) {
  if (texto(noticia.url_artigo)) return noticia.url_artigo;
  const doi = texto(noticia.doi).replace(/^https?:\/\/(dx\.)?doi\.org\//i, '');
  return doi ? `https://doi.org/${doi}` : '';
}

function metaHtml(noticia) {
  const itens = [];
  if (texto(noticia.autores)) itens.push(`<span><i class="fa-solid fa-user-pen" aria-hidden="true"></i>${escaparHtml(noticia.autores)}</span>`);
  if (noticia.ano) itens.push(`<span><i class="fa-solid fa-calendar" aria-hidden="true"></i>${escaparHtml(noticia.ano)}</span>`);
  return itens.join('');
}

function configurarAbas() {
  const lista = document.querySelector('[role="tablist"]');
  if (!lista) return;
  const botoes = [...lista.querySelectorAll('[role="tab"]')];

  function ativar(botao, focar = false) {
    botoes.forEach(item => {
      const selecionado = item === botao;
      item.setAttribute('aria-selected', String(selecionado));
      item.tabIndex = selecionado ? 0 : -1;
      const painel = document.getElementById(item.getAttribute('aria-controls'));
      if (painel) painel.hidden = !selecionado;
    });
    if (focar) botao.focus();
  }

  botoes.forEach((botao, indice) => {
    botao.addEventListener('click', () => ativar(botao));
    botao.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      let proximo = indice;
      if (event.key === 'ArrowRight') proximo = (indice + 1) % botoes.length;
      if (event.key === 'ArrowLeft') proximo = (indice - 1 + botoes.length) % botoes.length;
      if (event.key === 'Home') proximo = 0;
      if (event.key === 'End') proximo = botoes.length - 1;
      ativar(botoes[proximo], true);
    });
  });
}

function pararAudio() {
  window.speechSynthesis?.cancel();
  if (botaoAudioAtivo) {
    botaoAudioAtivo.classList.remove('is-playing');
    botaoAudioAtivo.innerHTML = '<i class="fa-solid fa-volume-high" aria-hidden="true"></i> Ouvir esta versão';
  }
  falaAtiva = null;
  botaoAudioAtivo = null;
}

function configurarAudio() {
  document.querySelectorAll('.audio-button').forEach(botao => {
    botao.addEventListener('click', () => {
      if (botaoAudioAtivo === botao) {
        pararAudio();
        return;
      }
      pararAudio();
      const alvo = document.getElementById(botao.dataset.target);
      if (!alvo || !alvo.textContent.trim() || !('speechSynthesis' in window)) return;

      falaAtiva = new SpeechSynthesisUtterance(alvo.textContent.trim());
      falaAtiva.lang = 'pt-BR';
      falaAtiva.rate = 1;
      botaoAudioAtivo = botao;
      botao.classList.add('is-playing');
      botao.innerHTML = '<i class="fa-solid fa-square" aria-hidden="true"></i> Parar áudio';
      falaAtiva.onend = falaAtiva.onerror = pararAudio;
      window.speechSynthesis.speak(falaAtiva);
    });
  });
}

function renderizarArtigo(noticia) {
  const destino = document.getElementById('artigo-root');
  const divulgacaoSalva = normalizarBlocosPublicados(noticia.divulgacao_cientifica_blocos);
  const divulgacaoSemantica = noticia.divulgacao_blocos_semanticos === true && divulgacaoSalva.length > 0;
  const blocosDivulgacao = divulgacaoSemantica
    ? divulgacaoSalva
    : estruturarDivulgacao(noticia.divulgacao_cientifica || noticia.leve || '');
  const blocosFacilitada = extrairLeituraFacilitada(noticia);
  const resumoCientifico = obterResumoCientifico(noticia);
  const fonte = urlFonteOriginal(noticia);
  const pdf = texto(noticia.url_pdf);
  const subtitulo = limparTexto(noticia.subtitulo || '');

  document.title = `${tituloNoticia(noticia)} — Jornal Cienc.IA`;

  destino.innerHTML = `
    <article>
      <header class="reader-header">
        <div class="reader-kicker">
          <span class="tag tag-primary">${escaparHtml(tipoPrincipal(noticia))}</span>
          <span class="tag">${escaparHtml(formatarTema(noticia.tema))}</span>
        </div>
        <h1 class="reader-title">${escaparHtml(tituloNoticia(noticia))}</h1>
        ${subtitulo ? `<p class="reader-subtitle">${escaparHtml(subtitulo)}</p>` : ''}
        <div class="article-meta reader-meta">${metaHtml(noticia)}</div>
      </header>

      <div class="reading-guide">
        <i class="fa-solid fa-circle-info" aria-hidden="true"></i>
        <span>Escolha a forma de leitura que for mais confortável. As três versões apresentam o mesmo estudo com níveis diferentes de linguagem.</span>
      </div>

      <section class="tabs" aria-label="Versões da matéria">
        <div class="tab-list" role="tablist" aria-label="Escolher versão de leitura">
          <button class="tab-button" id="tab-divulgacao" role="tab" aria-selected="true" aria-controls="painel-divulgacao">Divulgação científica</button>
          <button class="tab-button" id="tab-facilitada" role="tab" aria-selected="false" aria-controls="painel-facilitada" tabindex="-1">Leitura facilitada</button>
          <button class="tab-button" id="tab-resumo" role="tab" aria-selected="false" aria-controls="painel-resumo" tabindex="-1">Resumo científico</button>
        </div>

        <div class="tab-panel" id="painel-divulgacao" role="tabpanel" aria-labelledby="tab-divulgacao">
          <p class="panel-intro">Uma apresentação do estudo para o público geral.</p>
          <div class="${divulgacaoSemantica ? 'content-grid' : 'single-text-wrapper'}" id="texto-divulgacao">
            ${divulgacaoSemantica
              ? cardsHtml(blocosDivulgacao, 'divulgacao')
              : textoUnicoHtml((blocosDivulgacao[0] || {}).texto || '', 'divulgacao-legada')}
          </div>
          <button class="audio-button" type="button" data-target="texto-divulgacao"><i class="fa-solid fa-volume-high" aria-hidden="true"></i> Ouvir esta versão</button>
        </div>

        <div class="tab-panel" id="painel-facilitada" role="tabpanel" aria-labelledby="tab-facilitada" hidden>
          <p class="panel-intro">Frases mais diretas e organização em quatro partes para reduzir o esforço de leitura.</p>
          <div class="content-grid" id="texto-facilitada">${cardsHtml(blocosFacilitada, 'facilitada')}</div>
          <button class="audio-button" type="button" data-target="texto-facilitada"><i class="fa-solid fa-volume-high" aria-hidden="true"></i> Ouvir esta versão</button>
        </div>

        <div class="tab-panel" id="painel-resumo" role="tabpanel" aria-labelledby="tab-resumo" hidden>
          <p class="panel-intro">Tradução técnica do resumo científico preservada em português.</p>
          <div class="single-text-wrapper" id="texto-resumo">
            ${textoUnicoHtml(resumoCientifico, 'scientific-summary-card')}
          </div>
        </div>
      </section>

      <aside class="source-box" aria-labelledby="fonte-titulo">
        <h2 id="fonte-titulo">Quer consultar o estudo?</h2>
        <p>Acesse a publicação científica original usada como fonte desta matéria.</p>
        <div class="source-actions">
          ${fonte ? `<a class="button-link button-primary" href="${escaparHtml(fonte)}" target="_blank" rel="noopener noreferrer"><i class="fa-solid fa-arrow-up-right-from-square" aria-hidden="true"></i> Acessar artigo original</a>` : '<span>Link do artigo original não disponível.</span>'}
          ${pdf ? `<a class="button-link button-secondary" href="${escaparHtml(pdf)}" target="_blank" rel="noopener noreferrer"><i class="fa-regular fa-file-pdf" aria-hidden="true"></i> Abrir PDF</a>` : ''}
        </div>
      </aside>
    </article>`;

  configurarAbas();
  configurarAudio();
}

function mostrarErro(mensagem) {
  document.getElementById('artigo-root').innerHTML = `
    <div class="reader-error">
      <h1>Não foi possível abrir esta matéria</h1>
      <p>${escaparHtml(mensagem)}</p>
      <a class="button-link button-primary" href="index.html">Voltar para as notícias</a>
    </div>`;
}

async function inicializar() {
  const id = new URLSearchParams(window.location.search).get('id');
  if (!id) {
    mostrarErro('O endereço não informa qual artigo deve ser exibido.');
    return;
  }

  try {
    const resposta = await fetch('noticias.json', { cache: 'no-store' });
    if (!resposta.ok) throw new Error('Não foi possível carregar as notícias.');
    const dados = await resposta.json();
    const noticias = Array.isArray(dados) ? dados : [];
    const noticia = noticias.find(item => texto(item?.paper_id) === texto(id));
    if (!noticia) {
      mostrarErro('Esta matéria não foi encontrada entre as notícias publicadas.');
      return;
    }
    renderizarArtigo(noticia);
  } catch (erro) {
    mostrarErro('Tente novamente em alguns instantes.');
  }
}

window.addEventListener('beforeunload', pararAudio);
document.addEventListener('DOMContentLoaded', inicializar);
