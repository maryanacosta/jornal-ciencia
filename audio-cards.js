/* Jornal Cienc.IA — áudio individual dos cards.
 * Primeiro tenta o MP3 previamente salvo em audios/manifesto.json.
 * Se faltar ou o texto tiver mudado, usa a voz do navegador.
 * Não exige alterações em artigo.js nem nos dados científicos.
 */
(() => {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    const raiz = document.getElementById('artigo-root');
    if (!raiz) return;

    const sintese = window.speechSynthesis;
    const suportaVozDoNavegador = !!(sintese && window.SpeechSynthesisUtterance);
    const idArtigo = new URLSearchParams(window.location.search).get('id');
    let leituraAtiva = null;
    let numeroSolicitacao = 0;

    // Apenas uma leitura do manifesto por página, sem carregamento de MP3s até o clique.
    const manifestoPronto = fetch('audios/manifesto.json', { cache: 'no-store' })
      .then(resposta => resposta.ok ? resposta.json() : null)
      .catch(() => null);

    function textoDoCard(card) {
      return [...card.querySelectorAll('p')]
        .filter(p => !p.closest('button'))
        .map(p => p.textContent.replace(/\s+/g, ' ').trim())
        .filter(Boolean)
        .join(' ');
    }

    function atualizar(botao, estado = 'parado') {
      if (!botao || !botao.isConnected) return;
      const titulo = botao.dataset.audioTitulo || 'este trecho';
      const tocando = estado === 'tocando';
      const pausado = estado === 'pausado';
      const verbo = tocando ? 'Pausar' : pausado ? 'Continuar' : 'Ouvir';
      const icone = tocando ? 'fa-pause' : pausado ? 'fa-play' : 'fa-volume-high';
      botao.classList.toggle('is-playing', tocando);
      botao.classList.toggle('is-paused', pausado);
      botao.setAttribute('aria-pressed', String(tocando));
      botao.setAttribute('aria-label', `${verbo}: ${titulo}`);
      botao.title = `${verbo}: ${titulo}`;
      botao.innerHTML = `<i class="fa-solid ${icone}" aria-hidden="true"></i>`;
    }

    function parar() {
      ++numeroSolicitacao;
      const anterior = leituraAtiva;
      leituraAtiva = null;
      if (anterior) {
        atualizar(anterior.botao, 'parado');
        if (anterior.audio) {
          anterior.audio.pause();
          anterior.audio.onended = null;
          anterior.audio.onerror = null;
          anterior.audio.removeAttribute('src');
          anterior.audio.load();
        }
      }
      if (sintese) sintese.cancel();
    }

    function pontuacaoVoz(voz) {
      const nome = voz.name.toLowerCase();
      return (/natural|neural|premium/.test(nome) ? 20 : 0)
        + (/microsoft|google/.test(nome) ? 5 : 0) + (voz.default ? 2 : 0);
    }

    function vozBrasileira() {
      if (!sintese) return null;
      const vozes = sintese.getVoices();
      const portugues = vozes.filter(v => /^pt(?:[-_]|$)/i.test(v.lang));
      const brasileiras = portugues.filter(v => /^pt[-_]BR$/i.test(v.lang));
      const candidatas = brasileiras.length ? brasileiras : portugues;
      return [...candidatas].sort((a, b) => pontuacaoVoz(b) - pontuacaoVoz(a))[0] || null;
    }

    function dividirTrechos(conteudo) {
      const limite = 220;
      const frases = typeof Intl.Segmenter === 'function'
        ? [...new Intl.Segmenter('pt-BR', { granularity: 'sentence' }).segment(conteudo)].map(x => x.segment.trim()).filter(Boolean)
        : (conteudo.match(/[^.!?]+[.!?]*|[^.!?]+$/g) || [conteudo]).map(x => x.trim()).filter(Boolean);
      const partes = [];
      let atual = '';
      function enviar() { if (atual) partes.push(atual); atual = ''; }
      for (const frase of frases) {
        if (frase.length <= limite) {
          if (atual && atual.length + frase.length + 1 > limite) enviar();
          atual = atual ? `${atual} ${frase}` : frase;
          continue;
        }
        enviar();
        for (const palavra of frase.split(/\s+/)) {
          if (atual && atual.length + palavra.length + 1 > limite) enviar();
          atual = atual ? `${atual} ${palavra}` : palavra;
        }
        enviar();
      }
      enviar();
      return partes;
    }

    function continuarNavegador(sessao) {
      if (leituraAtiva !== sessao) return;
      if (sessao.indice >= sessao.trechos.length) return parar();
      const fala = new SpeechSynthesisUtterance(sessao.trechos[sessao.indice]);
      fala.lang = 'pt-BR';
      fala.rate = 0.96;
      const voz = vozBrasileira();
      if (voz) fala.voice = voz;
      fala.onend = () => {
        if (leituraAtiva !== sessao) return;
        ++sessao.indice;
        continuarNavegador(sessao);
      };
      fala.onerror = () => { if (leituraAtiva === sessao) parar(); };
      try { sintese.speak(fala); } catch (_) { parar(); }
    }

    function iniciarNavegador(botao, conteudo) {
      if (!suportaVozDoNavegador) {
        atualizar(botao, 'parado');
        window.alert('Não há áudio disponível neste dispositivo para este trecho.');
        return;
      }
      const sessao = { botao, tipo: 'navegador', indice: 0, trechos: dividirTrechos(conteudo) };
      leituraAtiva = sessao;
      atualizar(botao, 'tocando');
      continuarNavegador(sessao);
    }

    async function iniciarMP3(botao, conteudo, url) {
      const audio = new Audio(url);
      audio.preload = 'none';
      const sessao = { botao, tipo: 'mp3', audio };
      leituraAtiva = sessao;
      atualizar(botao, 'tocando');
      audio.onended = () => { if (leituraAtiva === sessao) parar(); };
      audio.onerror = () => {
        if (leituraAtiva !== sessao) return;
        parar();
        iniciarNavegador(botao, conteudo);
      };
      try {
        await audio.play();
      } catch (erro) {
        if (leituraAtiva !== sessao) return;
        parar();
        // Se o arquivo local estiver indisponível, volta à voz do navegador.
        // Em caso de bloqueio de autoplay, não repetir com outra tecnologia.
        if (erro?.name !== 'NotAllowedError') iniciarNavegador(botao, conteudo);
      }
    }

    async function clicar(card, botao) {
      if (leituraAtiva?.botao === botao) {
        const sessao = leituraAtiva;
        if (sessao.tipo === 'mp3') {
          if (sessao.audio.paused) {
            try { await sessao.audio.play(); atualizar(botao, 'tocando'); }
            catch (_) { parar(); }
          } else {
            sessao.audio.pause();
            atualizar(botao, 'pausado');
          }
        } else if (sintese) {
          if (sintese.paused) { sintese.resume(); atualizar(botao, 'tocando'); }
          else { sintese.pause(); atualizar(botao, 'pausado'); }
        }
        return;
      }

      parar();
      const solicitacao = numeroSolicitacao;
      const conteudo = textoDoCard(card);
      if (!conteudo) return;
      const manifesto = await manifestoPronto;
      if (solicitacao !== numeroSolicitacao || !botao.isConnected) return;
      const entrada = manifesto?.artigos?.[idArtigo]?.[card.id];
      if (entrada && entrada.texto === conteudo && typeof entrada.arquivo === 'string' && /^audios\/[a-f0-9]{16}\/(divulgacao|facilitada)-\d+\.mp3$/.test(entrada.arquivo)) {
        iniciarMP3(botao, conteudo, entrada.arquivo);
      } else {
        iniciarNavegador(botao, conteudo);
      }
    }

    function inserirBotoes() {
      raiz.querySelectorAll('.content-card').forEach(card => {
        const cabecalho = card.querySelector('.content-heading');
        if (!cabecalho || cabecalho.querySelector('.card-audio-toggle')) return;
        if (!textoDoCard(card) || textoDoCard(card) === 'Informação não disponível.') return;
        const botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'card-audio-toggle';
        botao.dataset.audioTitulo = cabecalho.querySelector('h2,h3')?.textContent.trim() || 'este trecho';
        cabecalho.append(botao);
        atualizar(botao);
        botao.addEventListener('click', () => clicar(card, botao));
      });
    }

    const observador = new MutationObserver(() => {
      if (leituraAtiva && !leituraAtiva.botao.isConnected) parar();
      inserirBotoes();
    });
    observador.observe(raiz, { childList: true, subtree: true });
    inserirBotoes();

    // Interrompe um MP3 antes de o botao antigo 'Ouvir esta versao'
    // iniciar sua propria leitura via artigo.js (sem audio sobreposto).
    document.addEventListener('click', event => {
      if (event.target.closest('.audio-button')) parar();
    }, true);
    document.addEventListener('click', event => {
      if (event.target.closest('.tab-button, [role="tab"]')) parar();
    });
    window.addEventListener('pagehide', () => {
      observador.disconnect();
      parar();
    });
  });
})();
