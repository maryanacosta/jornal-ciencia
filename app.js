let todasNoticias = [];
let temaAtivo = '';
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

  /*
   * Compatibilidade com notícias antigas.
   *
   * A tradução normal dos temas agora deve vir pronta do backend
   * no campo "tema_exibicao".
   *
   * STI é uma exceção porque a sigla em português é IST.
   */
  if (chave === 'sti') {
    return 'IST';
  }

  return chave.charAt(0).toUpperCase() + chave.slice(1);
}

function temaExibicao(noticia) {
  /*
   * Prioridade:
   * 1. tema_exibicao traduzido automaticamente pelo backend;
   * 2. tema original como fallback para arquivos antigos.
   */
  return (
    texto(noticia && noticia.tema_exibicao) ||
    formatarTema(noticia && noticia.tema)
  );
}

function tipoPrincipal(noticia) {
  const tipos = Array.isArray(noticia.tipos)
    ? noticia.tipos
    : [];

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
  return `artigo.html?id=${encodeURIComponent(
    texto(noticia.paper_id)
  )}`;
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

function construirMenuTemas() {
  const nav = document.getElementById('lista-temas');

  if (!nav) {
    return;
  }

  /*
   * O valor original continua sendo utilizado como chave do filtro.
   * O rótulo traduzido é apresentado ao usuário.
   * A contagem ajuda a navegação quando a lista de temas cresce.
   */
  const temasPorOriginal = new Map();

  todasNoticias.forEach(noticia => {
    const original = texto(noticia.tema);

    if (!original) {
      return;
    }

    const atual = temasPorOriginal.get(original);

    if (atual) {
      atual.quantidade += 1;
      return;
    }

    temasPorOriginal.set(original, {
      rotulo: temaExibicao(noticia),
      quantidade: 1
    });
  });

  const temas = [...temasPorOriginal.entries()]
    .sort((a, b) =>
      a[1].rotulo.localeCompare(
        b[1].rotulo,
        'pt-BR',
        { sensitivity: 'base' }
      )
    );

  nav.innerHTML = '';

  const todos = document.createElement('button');

  todos.type = 'button';
  todos.className = 'topic-button is-active';
  todos.dataset.topic = '';

  todos.innerHTML = `
    <span>Todos os temas</span>
    <span
      class="topic-count"
      aria-label="${todasNoticias.length} notícias"
    >
      ${todasNoticias.length}
    </span>
  `;

  nav.appendChild(todos);

  temas.forEach(([temaOriginal, dados]) => {
    const botao = document.createElement('button');

    botao.type = 'button';
    botao.className = 'topic-button';
    botao.dataset.topic = temaOriginal;

    botao.innerHTML = `
      <span>${escaparHtml(dados.rotulo)}</span>
      <span
        class="topic-count"
        aria-label="${dados.quantidade} notícias"
      >
        ${dados.quantidade}
      </span>
    `;

    nav.appendChild(botao);
  });

  nav.addEventListener('click', event => {
    const botao = event.target.closest('.topic-button');

    if (!botao) {
      return;
    }

    temaAtivo = botao.dataset.topic || '';

    nav
      .querySelectorAll('.topic-button')
      .forEach(item =>
        item.classList.remove('is-active')
      );

    botao.classList.add('is-active');

    renderizar();

    if (
      window
        .matchMedia('(max-width: 820px)')
        .matches
    ) {
      const painel =
        document.getElementById('painel-temas');

      const alternar =
        document.getElementById('alternar-temas');

      painel?.classList.remove('is-open');

      alternar?.setAttribute(
        'aria-expanded',
        'false'
      );

      const rotulo =
        alternar?.querySelector('span');

      if (rotulo) {
        rotulo.textContent = 'Ver temas';
      }
    }
  });
}

function noticiasFiltradas() {
  return todasNoticias.filter(noticia => {
    const bateTema =
      !temaAtivo ||
      texto(noticia.tema) === temaAtivo;

    const indiceBusca = [
      noticia.manchete,
      noticia.titulo_pt,
      noticia.titulo_original,
      noticia.autores,
      noticia.tema,
      noticia.tema_exibicao,
    ]
      .map(texto)
      .join(' ')
      .toLowerCase();

    const bateBusca =
      !buscaAtiva ||
      indiceBusca.includes(buscaAtiva);

    return bateTema && bateBusca;
  });
}

function renderizar() {
  const destino =
    document.getElementById(
      'portal-noticias'
    );

  if (!destino) {
    return;
  }

  const noticias =
    noticiasFiltradas();

  if (!noticias.length) {
    destino.innerHTML = `
      <div class="empty-state">

        <i
          class="fa-regular fa-newspaper"
          aria-hidden="true"
        ></i>

        <h2>
          Nenhuma notícia encontrada
        </h2>

        <p>
          Tente outro tema ou termo de busca.
        </p>

      </div>
    `;

    return;
  }

  const [destaque, ...resto] =
    noticias;

  let html = `
    <a
      class="feature"
      href="${linkArtigo(destaque)}"
      aria-label="Ler: ${escaparHtml(
        tituloNoticia(destaque)
      )}"
    >

      <div class="feature-copy">

        <span class="feature-badge">

          <i
            class="fa-solid fa-star"
            aria-hidden="true"
          ></i>

          Destaque

        </span>

        <h2 class="feature-title">
          ${escaparHtml(
            tituloNoticia(destaque)
          )}
        </h2>

        <p class="feature-summary">
          ${escaparHtml(
            resumoCurto(destaque)
          )}
        </p>

        <div class="article-meta">
          ${metaHtml(destaque, true)}
        </div>

      </div>

      </div>

    </a>
  `;

  if (resto.length) {
    html += `
      <section
        class="list-section"
        aria-labelledby="titulo-lista"
      >

        <div class="section-heading">

          <h2
            class="section-title"
            id="titulo-lista"
          >
            Mais notícias científicas
          </h2>

          <span class="section-count">

            ${resto.length}

            ${
              resto.length === 1
                ? 'notícia'
                : 'notícias'
            }

          </span>

        </div>

        <div class="news-grid">
    `;

    resto.forEach(noticia => {
      html += `
        <a
          class="news-card"
          href="${linkArtigo(noticia)}"
          aria-label="Ler: ${escaparHtml(
            tituloNoticia(noticia)
          )}"
        >

          <div class="card-tags">

            <span class="tag tag-primary">
              ${escaparHtml(
                tipoPrincipal(noticia)
              )}
            </span>

            <span class="tag">
              ${escaparHtml(
                temaExibicao(noticia)
              )}
            </span>

          </div>

          <h3 class="card-title">
            ${escaparHtml(
              tituloNoticia(noticia)
            )}
          </h3>

          <p class="card-summary">
            ${escaparHtml(
              resumoCurto(noticia)
            )}
          </p>

          <div class="card-meta">
            ${metaHtml(noticia)}
          </div>

          <span class="card-cta">

            Ler matéria

            <i
              class="fa-solid fa-arrow-right"
              aria-hidden="true"
            ></i>

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
  const data =
    document.getElementById(
      'data-hoje'
    );

  if (data) {
    data.textContent =
      new Date().toLocaleDateString(
        'pt-BR',
        {
          weekday: 'long',
          day: 'numeric',
          month: 'long',
          year: 'numeric'
        }
      );
  }

  try {
    const resposta =
      await fetch(
        'noticias.json',
        {
          cache: 'no-store'
        }
      );

    if (!resposta.ok) {
      throw new Error(
        'Falha ao carregar notícias'
      );
    }

    const dados =
      await resposta.json();

    todasNoticias =
      Array.isArray(dados)
        ? dados.filter(
            item =>
              item &&
              typeof item === 'object'
          )
        : [];

  } catch (erro) {
    console.error(
      'Erro ao carregar noticias.json:',
      erro
    );

    todasNoticias = [];
  }

  construirMenuTemas();

  const painelTemas =
    document.getElementById(
      'painel-temas'
    );

  const alternarTemas =
    document.getElementById(
      'alternar-temas'
    );

  if (
    painelTemas &&
    alternarTemas
  ) {
    alternarTemas.addEventListener(
      'click',
      () => {
        const aberto =
          painelTemas.classList.toggle(
            'is-open'
          );

        alternarTemas.setAttribute(
          'aria-expanded',
          String(aberto)
        );

        const rotulo =
          alternarTemas.querySelector(
            'span'
          );

        if (rotulo) {
          rotulo.textContent =
            aberto
              ? 'Ocultar temas'
              : 'Ver temas';
        }
      }
    );
  }

  const busca =
    document.getElementById(
      'campo-busca'
    );

  if (busca) {
    busca.addEventListener(
      'input',
      event => {
        buscaAtiva =
          event.target.value
            .toLowerCase()
            .trim();

        renderizar();
      }
    );
  }

  renderizar();
}

document.addEventListener(
  'DOMContentLoaded',
  inicializar
);