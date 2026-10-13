
let todasNoticias = [];
let modoExploracao = 'temas';
let filtroAtivo = '';
let buscaAtiva = '';

function texto(valor) {
  return valor === undefined || valor === null ? '' : String(valor).trim();
}

function escaparHtml(valor) {
  return texto(valor)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function limparTexto(valor) {
  return texto(valor)
    .replace(/\\n/g, '\n')
    .replace(/\r/g, '')
    .replace(/\t/g, ' ')
    .replace(/\*\*/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function formatarTema(valor) {
  const chave = texto(valor)
    .toLowerCase()
    .replace(/_/g, ' ')
    .trim();

  if (!chave) {
    return 'Geral';
  }

  if (chave === 'sti') {
    return 'IST';
  }

  return chave.charAt(0).toUpperCase() + chave.slice(1);
}

function temaExibicao(noticia) {
  return (
    texto(noticia && noticia.tema_exibicao) ||
    formatarTema(noticia && noticia.tema)
  );
}

function origemBusca(noticia) {
  const origem =
    noticia && noticia.origem_busca && typeof noticia.origem_busca === 'object'
      ? noticia.origem_busca
      : {};

  const tipo = texto(
    origem.tipo ||
    noticia?.tipo_origem_busca ||
    noticia?.origem_tipo
  ).toLowerCase();

  const entradaOriginal = texto(
    origem.entrada_original ||
    noticia?.pergunta_original ||
    noticia?.pergunta_origem ||
    noticia?.pergunta
  );

  const perguntaFormal = texto(
    origem.pergunta_formal ||
    noticia?.pergunta_formal
  );

  return {
    tipo,
    entradaOriginal,
    perguntaFormal
  };
}

function perguntaExibicao(noticia) {
  const origem = origemBusca(noticia);
  return origem.entradaOriginal || origem.perguntaFormal;
}

function ehNoticiaDePergunta(noticia) {
  const origem = origemBusca(noticia);
  return origem.tipo === 'pergunta' || Boolean(origem.entradaOriginal);
}

function tipoPrincipal(noticia) {
  const tipos = Array.isArray(noticia.tipos) ? noticia.tipos : [];

  return (
    tipos[0] ||
    noticia.desenho_estudo_rotulo ||
    'Artigo científico'
  );
}

function tituloNoticia(noticia) {
  return texto(
    noticia.manchete ||
    noticia.titulo_pt ||
    noticia.titulo_original ||
    'Sem título'
  );
}

function resumoCurto(noticia) {
  const fonte = limparTexto(
    noticia.divulgacao_cientifica ||
    noticia.leve ||
    noticia.leitura_facilitada ||
    noticia.forte ||
    noticia.resumo_cientifico_traduzido ||
    noticia.abstract_pt ||
    ''
  );

  const semTitulos = fonte
    .replace(
      /^(O principal|O que o artigo fez|O que foi encontrado|O que ainda não sabemos)\s*[:\-]?\s*$/gim,
      ''
    )
    .replace(/\n+/g, ' ')
    .trim();

  if (semTitulos.length <= 240) {
    return semTitulos;
  }

  return `${semTitulos.slice(0, 237).trim()}…`;
}

function linkArtigo(noticia) {
  return `artigo.html?id=${encodeURIComponent(texto(noticia.paper_id))}`;
}

function metaHtml(noticia, destaque = false) {
  const itens = [];

  if (texto(noticia.autores)) {
    itens.push(`
      <span>
        <i class="fa-solid fa-user-pen" aria-hidden="true"></i>
        ${escaparHtml(noticia.autores)}
      </span>
    `);
  }

  if (noticia.ano) {
    itens.push(`
      <span>
        <i class="fa-solid fa-calendar" aria-hidden="true"></i>
        ${escaparHtml(noticia.ano)}
      </span>
    `);
  }

  if (!destaque) {
    itens.push(`
      <span>
        <i class="fa-solid fa-book-open" aria-hidden="true"></i>
        ${escaparHtml(tipoPrincipal(noticia))}
      </span>
    `);
  }

  return itens.join('');
}

function contextoPerguntaHtml(noticia) {
  if (modoExploracao !== 'perguntas') {
    return '';
  }

  const pergunta = perguntaExibicao(noticia);
  if (!pergunta) {
    return '';
  }

  return `
    <div class="question-origin">
      <i class="fa-regular fa-circle-question" aria-hidden="true"></i>
      <span>${escaparHtml(pergunta)}</span>
    </div>
  `;
}

function opcoesExploracao(modo) {
  const mapa = new Map();

  todasNoticias.forEach(noticia => {
    if (modo === 'perguntas' && !ehNoticiaDePergunta(noticia)) {
      return;
    }

    const chave = modo === 'perguntas'
      ? perguntaExibicao(noticia)
      : texto(noticia.tema);

    if (!chave) {
      return;
    }

    const existente = mapa.get(chave);

    mapa.set(chave, {
      chave,
      rotulo: modo === 'perguntas' ? chave : temaExibicao(noticia),
      quantidade: (existente?.quantidade || 0) + 1
    });
  });

  return [...mapa.values()].sort((a, b) =>
    a.rotulo.localeCompare(b.rotulo, 'pt-BR', { sensitivity: 'base' })
  );
}

function construirMenuExploracao() {
  for (const modo of ['temas', 'perguntas']) {
    const nav = document.getElementById(`lista-${modo}`);

    if (!nav) {
      continue;
    }

    nav.innerHTML = '';

    const opcoes = opcoesExploracao(modo);

    if (modo === 'perguntas' && !opcoes.length) {
      const vazio = document.createElement('p');
      vazio.className = 'sidebar-empty';
      vazio.textContent = 'Ainda não há perguntas publicadas.';
      nav.appendChild(vazio);
      continue;
    }

    const total = modo === 'perguntas'
      ? todasNoticias.filter(ehNoticiaDePergunta).length
      : todasNoticias.length;

    const todas = [{
      chave: '',
      rotulo: modo === 'perguntas'
        ? 'Todas as perguntas'
        : 'Todos os temas',
      quantidade: total
    }, ...opcoes];

    todas.forEach(opcao => {
      const botao = document.createElement('button');
      botao.type = 'button';
      botao.className = 'topic-button';

      const ativo =
        modoExploracao === modo && filtroAtivo === opcao.chave;

      botao.classList.toggle('is-active', ativo);
      botao.dataset.topic = opcao.chave;

      botao.innerHTML = `
        <span>${escaparHtml(opcao.rotulo)}</span>
        <span class="topic-count">${opcao.quantidade}</span>
      `;

      nav.appendChild(botao);
    });
  }
}

function fecharMenuMobile() {
  if (!window.matchMedia('(max-width: 820px)').matches) {
    return;
  }

  document.getElementById('painel-temas')?.classList.remove('is-open');

  document.getElementById('alternar-temas')
    ?.setAttribute('aria-expanded', 'false');

  const rotulo = document.getElementById('rotulo-alternar-exploracao');

  if (rotulo) {
    rotulo.textContent = 'Ver opções';
  }
}

function configurarMenuExploracao() {
  for (const modo of ['temas', 'perguntas']) {
    const nav = document.getElementById(`lista-${modo}`);

    nav?.addEventListener('click', event => {
      const botao = event.target.closest('.topic-button');

      if (!botao) {
        return;
      }

      modoExploracao = modo;
      filtroAtivo = botao.dataset.topic || '';

      construirMenuExploracao();
      renderizar();
      fecharMenuMobile();
    });
  }
}

function noticiasFiltradas() {
  return todasNoticias.filter(noticia => {
    let bateModo = true;
    let bateFiltro = true;

    if (modoExploracao === 'perguntas') {
      bateModo = ehNoticiaDePergunta(noticia);
      bateFiltro =
        !filtroAtivo || perguntaExibicao(noticia) === filtroAtivo;
    } else {
      bateFiltro =
        !filtroAtivo || texto(noticia.tema) === filtroAtivo;
    }

    const origem = origemBusca(noticia);

    const indiceBusca = [
      noticia.manchete,
      noticia.titulo_pt,
      noticia.titulo_original,
      noticia.autores,
      noticia.tema,
      noticia.tema_exibicao,
      origem.entradaOriginal,
      origem.perguntaFormal,
    ]
      .map(texto)
      .join(' ')
      .toLowerCase();

    const bateBusca =
      !buscaAtiva || indiceBusca.includes(buscaAtiva);

    return bateModo && bateFiltro && bateBusca;
  });
}

function renderizar() {
  const destino = document.getElementById('portal-noticias');

  if (!destino) {
    return;
  }

  const noticias = noticiasFiltradas();

  if (!noticias.length) {
    const mensagem = modoExploracao === 'perguntas'
      ? 'Ainda não há matérias publicadas para esta pergunta.'
      : 'Tente outro tema ou termo de busca.';

    destino.innerHTML = `
      <div class="empty-state">
        <i class="fa-regular fa-newspaper" aria-hidden="true"></i>
        <h2>Nenhuma notícia encontrada</h2>
        <p>${mensagem}</p>
      </div>
    `;

    return;
  }

  const [destaque, ...resto] = noticias;

  let html = `
    <a
      class="feature"
      href="${linkArtigo(destaque)}"
      aria-label="Ler: ${escaparHtml(tituloNoticia(destaque))}"
    >
      <div class="feature-copy">
        <span class="feature-badge">
          <i class="fa-solid fa-star" aria-hidden="true"></i>
          Destaque
        </span>

        ${contextoPerguntaHtml(destaque)}

        <h2 class="feature-title">
          ${escaparHtml(tituloNoticia(destaque))}
        </h2>

        <p class="feature-summary">
          ${escaparHtml(resumoCurto(destaque))}
        </p>

        <div class="article-meta">
          ${metaHtml(destaque, true)}
        </div>
      </div>
    </a>
  `;

  if (resto.length) {
    html += `
      <section class="list-section" aria-labelledby="titulo-lista">
        <div class="section-heading">
          <h2 class="section-title" id="titulo-lista">
            Mais notícias científicas
          </h2>

          <span class="section-count">
            ${resto.length}
            ${resto.length === 1 ? 'notícia' : 'notícias'}
          </span>
        </div>

        <div class="news-grid">
    `;

    resto.forEach(noticia => {
      html += `
        <a
          class="news-card"
          href="${linkArtigo(noticia)}"
          aria-label="Ler: ${escaparHtml(tituloNoticia(noticia))}"
        >
          ${contextoPerguntaHtml(noticia)}

          <div class="card-tags">
            <span class="tag tag-primary">
              ${escaparHtml(tipoPrincipal(noticia))}
            </span>

            <span class="tag">
              ${escaparHtml(temaExibicao(noticia))}
            </span>
          </div>

          <h3 class="card-title">
            ${escaparHtml(tituloNoticia(noticia))}
          </h3>

          <p class="card-summary">
            ${escaparHtml(resumoCurto(noticia))}
          </p>

          <div class="card-meta">
            ${metaHtml(noticia)}
          </div>

          <span class="card-cta">
            Ler matéria
            <i class="fa-solid fa-arrow-right" aria-hidden="true"></i>
          </span>
        </a>
      `;
    });

    html += `
        </div>
      </section>
    `;
  }

  destino.innerHTML = html;
}

async function inicializar() {
  const data = document.getElementById('data-hoje');

  if (data) {
    data.textContent = new Date().toLocaleDateString('pt-BR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  }

  try {
    const resposta = await fetch('noticias.json', {
      cache: 'no-store'
    });

    if (!resposta.ok) {
      throw new Error('Falha ao carregar notícias');
    }

    const dados = await resposta.json();

    todasNoticias = Array.isArray(dados)
      ? dados.filter(item => item && typeof item === 'object')
      : [];
  } catch (erro) {
    console.error('Erro ao carregar noticias.json:', erro);
    todasNoticias = [];
  }

  configurarMenuExploracao();
  construirMenuExploracao();

  const painelTemas = document.getElementById('painel-temas');
  const alternarTemas = document.getElementById('alternar-temas');

  if (painelTemas && alternarTemas) {
    alternarTemas.addEventListener('click', () => {
      const aberto = painelTemas.classList.toggle('is-open');

      alternarTemas.setAttribute('aria-expanded', String(aberto));

      const rotulo = document.getElementById(
        'rotulo-alternar-exploracao'
      );

      if (rotulo) {
        rotulo.textContent = aberto
          ? 'Ocultar opções'
          : 'Ver opções';
      }
    });
  }

  const busca = document.getElementById('campo-busca');

  if (busca) {
    busca.addEventListener('input', event => {
      buscaAtiva = event.target.value.toLowerCase().trim();
      renderizar();
    });
  }

  renderizar();
}

document.addEventListener('DOMContentLoaded', inicializar);
