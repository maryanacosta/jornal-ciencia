# 📰 Jornal Cienc.IA

**Ciência em saúde, clara e fiel à evidência.**

Plataforma experimental de divulgação científica em saúde desenvolvida no contexto de Trabalho de Conclusão de Curso (TCC). O sistema coleta resumos de artigos biomédicos, organiza uma fila editorial, gera diferentes formas de leitura com apoio de modelos de linguagem, realiza checagens automáticas de fidelidade e acessibilidade textual e mantém a decisão final de publicação sob responsabilidade humana.

---

## 1. O que é o Jornal Cienc.IA

O Jornal Cienc.IA foi criado para investigar como modelos de linguagem podem apoiar a transformação de conteúdo científico biomédico em textos mais acessíveis para diferentes perfis de leitores sem abandonar informações essenciais da fonte.

O projeto parte de uma ideia central: **simplificar um texto científico não significa apenas encurtá-lo**. O sistema tenta reduzir a dificuldade linguística ao mesmo tempo em que preserva fatos, números, desenho do estudo, limitações, relações lógicas e grau de certeza presentes no resumo científico original.

O fluxo não é totalmente automático. A inteligência artificial produz e avalia rascunhos, mas **nenhum texto deve ser considerado correto ou adequado para publicação apenas porque recebeu uma boa pontuação automática**. O painel foi construído segundo um modelo *human-in-the-loop*:

```text
artigo científico
       ↓
coleta e triagem editorial
       ↓
tradução-base
       ↓
ficha estruturada de evidência
       ↓
geração dos textos
       ↓
checagem de simplificação e fidelidade
       ↓
REVISÃO HUMANA
       ↓
publicação no Jornal Cienc.IA
```

---

## 2. Objetivo da plataforma

O objetivo computacional da plataforma é apoiar a produção de conteúdos de divulgação científica em saúde em diferentes níveis de acessibilidade textual, mantendo rastreabilidade em relação ao conteúdo científico utilizado como fonte.

A implementação atual trabalha principalmente com **resumos científicos (abstracts)**. Mesmo quando o coletor identifica um link para texto completo ou PubMed Central, a geração editorial descrita neste README permanece centrada no resumo fornecido ao revisor.

A plataforma não deve ser apresentada como sistema de diagnóstico médico, recomendação clínica, checador universal de verdade ou substituto da leitura crítica de um artigo científico.

---

## 3. Princípios metodológicos

O funcionamento do Jornal Cienc.IA segue alguns princípios importantes:

1. **Fonte primeiro** — os conteúdos gerados devem ser sustentados pelo resumo científico utilizado como fonte.
2. **Sem conhecimento externo na geração editorial** — uma informação pode ser verdadeira em termos gerais e ainda assim ser inadequada para aquele rascunho se não estiver sustentada pela fonte analisada.
3. **Preservação da incerteza** — associação não deve virar causalidade; hipótese não deve virar conclusão; evidência limitada não deve virar certeza.
4. **Preservação de números relevantes** — quantidades, percentuais, medidas e resultados importantes não devem ser apagados apenas para deixar o texto menor.
5. **Simplificação da forma antes da remoção de conteúdo** — informações difíceis devem, sempre que possível, ser reescritas ou descompactadas em frases menores.
6. **Rastreabilidade** — o painel registra modelos usados, ficha de evidência, checagens, métricas auxiliares e decisões editoriais.
7. **Revisão humana obrigatória** — a automação auxilia a decisão; não substitui o revisor.

A regra central da Leitura Facilitada é:

> **Não remova uma informação apenas porque ela é difícil: explique-a.**

---

## 4. Componentes principais

O projeto possui três componentes funcionais principais.

### 4.1 Coletor biomédico

Arquivo principal:

```text
coletor_artigos.py
```

Responsável por buscar artigos, deduplicar registros, enriquecer metadados, calcular prioridade editorial e gerar:

```text
artigos_coletados.json
```

### 4.2 Painel editorial

Arquivo principal:

```text
revisor_jornal_ciencia.py
```

Aplicação Streamlit utilizada para:

- visualizar os artigos coletados;
- gerar rascunhos;
- editar manchete, subtítulo e textos;
- inspecionar a fonte e a ficha estruturada;
- consultar checagens de simplificação;
- consultar a auditoria de Fidelidade Intelectual;
- salvar e reavaliar alterações humanas;
- aprovar e publicar;
- rejeitar, reconsiderar ou despublicar conteúdos.

### 4.3 Portal público

Arquivo principal:

```text
index.html
```

O portal lê o arquivo:

```text
noticias.json
```

Somente os conteúdos efetivamente publicados pelo painel aparecem no portal público.

---

## 5. Estrutura recomendada da pasta

Uma organização típica é:

```text
jornal-ciencia/
│
├── coletor_artigos.py
├── revisor_jornal_ciencia.py
├── index.html
├── .env
├── .gitignore
│
├── artigos_coletados.json
├── noticias.json
├── rascunhos.json
├── estado_editorial.json
├── historico_editorial.json
├── traducoes_base.json
│
└── README.md
```

Alguns arquivos JSON podem ser criados automaticamente quando o painel é utilizado. Se estiver iniciando um experimento novo, recomenda-se criá-los ou reiniciá-los explicitamente conforme a seção de limpeza deste README.

---

# 6. Coleta biomédica

## 6.1 Fontes de descoberta

Os artigos que podem entrar na fila editorial são descobertos em bases biomédicas:

- **PubMed**;
- **Europe PMC**;
- **Embase**, quando a API está autorizada para a conta/instituição.

O Embase é opcional. Se a API não estiver disponível, o coletor continua funcionando com PubMed e Europe PMC.

## 6.2 Fontes de enriquecimento

As seguintes bases são usadas para complementar registros já descobertos nas fontes biomédicas:

- Semantic Scholar;
- OpenAlex;
- Crossref.

Essas fontes **não devem introduzir sozinhas novos artigos na fila editorial**. Elas servem para completar metadados, como DOI, citações, informações de acesso e outros dados bibliográficos quando houver correspondência com um registro já encontrado.

Essa separação é importante:

```text
PubMed / Europe PMC / Embase
             ↓
      DESCOBERTA BIOMÉDICA
             ↓
        deduplicação
             ↓
Semantic Scholar / OpenAlex / Crossref
             ↓
          ENRIQUECIMENTO
```

## 6.3 Deduplicação

O coletor tenta reconhecer o mesmo artigo encontrado em diferentes fontes.

A prioridade é:

1. DOI normalizado;
2. quando não há DOI, título normalizado.

Assim, um artigo localizado no PubMed e no Europe PMC deve permanecer como um único registro, preservando a informação sobre as fontes em que foi encontrado.

## 6.4 PubMed Central

Quando há PMCID, o coletor pode registrar o endereço correspondente no PubMed Central como possível acesso ao texto completo.

O PMC não funciona, na implementação atual, como uma quarta fonte independente de descoberta.

## 6.5 Busca por temas

O coletor **ainda utiliza temas de busca**. Há temas padrão definidos em `TEMAS_PADRAO`, e também é possível informar temas manualmente pela linha de comando.

Exemplo:

```bash
python coletor_artigos.py --temas "nutrition diet health outcomes" "vaccine safety adverse effects"
```

Portanto, uma coleta totalmente ampla e sem tema ainda **não faz parte da implementação atual**. Se essa estratégia for adicionada futuramente, a alteração metodológica deverá ser registrada e descrita neste README.

## 6.6 Prioridade editorial

Depois da descoberta e do enriquecimento, o sistema calcula uma **prioridade editorial operacional**.

Ela combina sinais como:

- desenho do estudo identificado nos metadados;
- atualidade;
- impacto bibliométrico atenuado por transformação logarítmica;
- disponibilidade de acesso;
- relevância/posição retornada pelas fontes.

O limiar de prioridade editorial é fixo:

```python
MIN_PRIORIDADE_EDITORIAL = 60.0
```

Todo registro elegível com prioridade igual ou superior a 60 pode entrar na fila editorial.

**Importante:** essa pontuação não deve ser interpretada como “qualidade científica”, “certeza da evidência” ou “nível OCEBM automático”. Ela apenas organiza a fila de leitura com base em sinais operacionais.

Não há um número máximo fixo de artigos selecionados por tema. O parâmetro `--limite-busca` controla quantos resultados cada fonte consulta antes da triagem, e não quantos artigos podem ser selecionados no final.

---

# 7. Como executar o coletor

## Coleta padrão

```bash
python coletor_artigos.py
```

O arquivo de saída padrão é:

```text
artigos_coletados.json
```

## Aumentar o número de registros consultados por fonte

```bash
python coletor_artigos.py --limite-busca 300
```

O valor maior aumenta o universo consultado antes da triagem. Ele não significa “selecionar 300 artigos”.

## Informar temas próprios

```bash
python coletor_artigos.py --temas "diet migraine" "cardiovascular prevention"
```

## Alterar o nome do arquivo de saída

```bash
python coletor_artigos.py --saida minha_coleta.json
```

Se usar outro nome, lembre-se de que o revisor procura por `artigos_coletados.json` para localizar a base principal. Para o fluxo normal da plataforma, mantenha o nome padrão.

---

# 8. Embase

O Embase exige mais do que possuir uma chave genérica da Elsevier. O acesso programático à API pode depender de *entitlement* institucional e, em alguns casos, de token institucional.

Configure no `.env`:

```env
EMBASE_API_KEY=
EMBASE_INSTTOKEN=
ATIVAR_EMBASE=1
```

Antes da coleta, pode-se testar:

```bash
python coletor_artigos.py --testar-embase
```

Interpretação prática:

- `HTTP 200`: acesso programático confirmado;
- `HTTP 401`: credencial inválida ou não reconhecida;
- `HTTP 403`: a credencial chegou à API, mas o acesso ao Embase não está autorizado para aquela conta/instituição;
- `HTTP 429`: limite temporário de requisições.

Um login institucional que funciona no site do Embase não garante automaticamente acesso à API.

---

# 9. Tradução-base

Antes da geração dos textos em português, o revisor cria uma **tradução-base fixa** do resumo original.

Essa tradução utiliza exclusivamente:

```text
Google Translate via deep-translator
```

Gemini e Groq **não são usados como tradutores** nessa etapa.

## 9.1 Por que a tradução é separada das LLMs?

A separação melhora a padronização experimental. O mesmo abstract pode reutilizar a mesma tradução-base mesmo que modelos generativos diferentes sejam acionados posteriormente.

## 9.2 Cache persistente

As traduções ficam em:

```text
traducoes_base.json
```

A identificação considera o artigo e o hash do abstract original.

Consequências:

- excluir um rascunho **não** exclui automaticamente sua tradução;
- gerar novamente o mesmo artigo pode reutilizar exatamente a mesma tradução-base;
- se o abstract mudar, uma nova tradução é produzida.

## 9.3 Falhas do Google Translate

A aplicação tenta novamente em caso de falha usando intervalos aproximados de:

```text
imediatamente → 3 s → 8 s → 20 s
```

Mensagens ou páginas curtas que aparentam ser erros `500`, `502`, `503` ou `504` não são aceitas como se fossem texto científico.

Se todas as tentativas falharem, o rascunho não deve prosseguir usando uma LLM como tradutor substituto. Isso evita misturar métodos de tradução dentro do mesmo experimento.

---

# 10. Ficha Estruturada de Evidência

Depois da tradução-base, uma LLM extrai uma representação estruturada do conteúdo relevante do resumo.

A ficha pode conter:

```text
TIPO DO ESTUDO
OBJETIVO
CONTEXTO
POPULAÇÃO
INTERVENÇÃO OU EXPOSIÇÃO
COMPARADOR
RESULTADOS PRINCIPAIS
NÚMEROS IMPORTANTES
LIMITAÇÕES
INCERTEZAS
TERMOS TÉCNICOS ESSENCIAIS
O QUE NÃO PODE SER CONCLUÍDO
INFORMAÇÕES AUSENTES
```

Quando uma informação não aparece na fonte, ela não deve ser completada por plausibilidade.

A ficha funciona como estrutura auxiliar para geração, simplificação e auditoria. Ela também pode ser revisada pelo usuário no painel.

As ideias de representação biomédica estruturada e rastreabilidade são inspiradas em trabalhos como FactPICO e FaReBio, mas o Jornal Cienc.IA **não implementa integralmente esses benchmarks**.

---

# 11. Os três modos de leitura

O Jornal Cienc.IA publica três formas de acessar o mesmo conteúdo científico.

## 11.1 Divulgação científica — N1

Voltada ao público geral adulto.

Características esperadas:

- texto jornalístico curto;
- mensagem principal apresentada cedo;
- explicação do que o estudo fez e encontrou;
- termos técnicos explicados quando a própria fonte permite;
- preservação de números e limitações importantes;
- ausência de sensacionalismo;
- nenhuma recomendação clínica inventada;
- associação não transformada em causalidade.

O N1 pode usar uma linguagem mais natural e jornalística que o resumo técnico, mas continua sujeito à regra *source-only*.

## 11.2 Leitura Facilitada — N2

O N2 é destinado a adultos que se beneficiam de menor complexidade textual e menor carga de inferência.

Ele é **gerado diretamente da fonte + tradução-base + ficha + plano de simplificação**. O N1 não é usado como texto intermediário. Essa independência reduz o risco de uma omissão ou erro da divulgação ser propagado automaticamente para a leitura mais simples.

A estrutura pública possui quatro blocos:

```text
O principal
O que o artigo fez
O que foi encontrado
O que ainda não sabemos
```

### Metas linguísticas atuais do N2

- faixa preferencial de aproximadamente **7 a 14 palavras por frase**;
- **16 palavras** como limite suave;
- frases com mais de **18 palavras** entram como alerta para possível divisão;
- uma ideia principal por frase;
- preferência por ordem direta;
- preferência por palavras mais concretas e cotidianas;
- redução de nominalizações e estruturas densas;
- redução de pronomes ambíguos;
- explicação de termos técnicos apenas quando a fonte permite;
- preservação de números, achados e incertezas essenciais.

Esses limites são **parâmetros operacionais**, não leis linguísticas e nem prova de compreensão humana.

Uma frase não deve ser quebrada se isso destruir o sentido ou produzir uma afirmação cientificamente errada.

### Expansão explicativa controlada

O N2 pode ficar maior que o N1.

Exemplo conceitual:

```text
frase científica densa
        ↓
2 ou 3 frases mais curtas
        ↓
mesma informação científica
```

O objetivo é reduzir o esforço necessário para compreender a informação, e não simplesmente minimizar o número de palavras.

### Termos técnicos

O plano de simplificação pode distinguir:

```text
termos_tecnicos_essenciais
termos_para_atencao
termos_evitar_quando_possivel
```

Se um termo é essencial e não pode ser explicado com segurança usando a própria fonte, ele deve ser mantido e sinalizado para revisão humana.

## 11.3 Resumo científico em português

É a forma de leitura mais próxima do abstract original.

Seu objetivo é produzir uma tradução técnica natural em português brasileiro, preservando:

- métodos;
- números;
- resultados;
- qualificadores;
- limitações;
- grau de certeza.

Esse texto **não é a leitura simplificada**. Ele serve também como apoio ao revisor que deseja comparar a fonte estrangeira com uma tradução técnica em português.

---

# 12. Checagem automática do N2

Antes da auditoria final de fidelidade, o N2 passa por uma checagem específica.

O sistema verifica, entre outros pontos:

- presença dos fatos considerados obrigatórios;
- possível perda de números relevantes;
- termos técnicos ainda difíceis;
- frases longas;
- frases com várias ideias;
- nominalizações densas;
- ambiguidades;
- complexidade desnecessária.

Se houver um problema considerado reparável, o sistema pode executar **uma única rodada automática de reparo**, preferencialmente apenas nos blocos afetados.

O limite de uma rodada evita um ciclo indefinido de reescritas, pois toda nova geração também pode introduzir uma nova distorção.

Após um reparo, o texto é rechecado antes de seguir para a auditoria de Fidelidade Intelectual.

---

# 13. Fidelidade Intelectual

A plataforma utiliza uma medida operacional denominada **Fidelidade Intelectual (FI)**.

Ela foi criada para organizar a revisão e não deve ser apresentada como métrica universal validada.

A fórmula é:

```text
FI = 0,50 × Sustentação
   + 0,25 × Cobertura
   + 0,25 × Preservação da Incerteza
```

## 13.1 Sustentação

Pergunta principal:

> As afirmações presentes no texto gerado encontram suporte no material usado como fonte?

## 13.2 Cobertura

Pergunta principal:

> Os elementos essenciais da fonte continuam presentes no texto?

## 13.3 Preservação da incerteza

Pergunta principal:

> O texto mantém o mesmo grau de certeza, possibilidade, associação, limitação e não-conclusão da fonte?

## 13.4 Nota geral

A pontuação geral é tratada de forma conservadora e considera o desempenho das diferentes formas de leitura. Um texto com bom desempenho não deve esconder problemas encontrados em outra forma de leitura.

## 13.5 Distorções epistemológicas

Uma alteração de sentido importante pode afetar Sustentação e/ou Preservação da Incerteza.

O projeto possui penalizações determinísticas operacionais para distorções confirmadas. Esses valores são escolhas metodológicas do projeto e não escalas validadas externamente.

Além disso, julgamentos negativos devem possuir rastreabilidade: o auditor deve indicar concretamente o trecho avaliado e o trecho da fonte utilizado como evidência. Alertas que não podem ser vinculados ao próprio texto/fonte não devem ser tratados automaticamente como prova de erro.

---

# 14. Status editorial gerado pela auditoria

A auditoria pode produzir status como:

```text
Aprovável após revisão humana
Revisão obrigatória
Bloqueado para publicação
```

Esses estados ajudam a priorizar a conferência.

Mesmo um rascunho marcado como “Aprovável” ainda exige revisão humana.

Um rascunho bloqueado pode exigir uma **justificativa explícita de publicação excepcional** no painel caso o revisor decida publicá-lo apesar do alerta. Essa possibilidade existe para manter a autoridade editorial humana, mas a decisão deve ser documentada.

---

# 15. MiniLM e recuperação semântica

Modelo padrão:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

O MiniLM é usado como mecanismo auxiliar de **recuperação semântica de evidências**.

Ele não deve ser descrito como “detector de verdade” nem como “percentual de fidelidade”.

## 15.1 Funcionamento

Os textos gerados e a fonte são segmentados em sentenças ou pequenos trechos.

Para cada unidade gerada, o sistema busca trechos semanticamente próximos em dois canais:

1. fonte original;
2. tradução-base em português.

A fonte original continua sendo a autoridade científica. A tradução serve como apoio linguístico para recuperação.

## 15.2 Recuperação bilíngue

A configuração atual utiliza até cinco candidatos por unidade gerada, procurando manter, quando ambos os canais existem:

```text
3 candidatos da fonte original
+
2 candidatos da tradução-base
```

Depois, os candidatos podem ser reorganizados por similaridade para exibição e auditoria.

## 15.3 Interpretação correta

Uma similaridade de `0.82`, por exemplo, **não significa “82% fiel”**.

O valor apenas indica proximidade vetorial dentro daquela comparação semântica.

O MiniLM ajuda o revisor e o auditor a localizar onde uma afirmação pode estar sustentada. A avaliação factual depende da fonte completa, da ficha estruturada e da revisão humana.

## 15.4 Limite de sequência

A configuração utilizada pelo pacote Sentence Transformers para esse modelo trabalha com `max_seq_length = 128` tokens.

Por isso, a plataforma compara sentenças/trechos em vez de codificar resumos longos como um único bloco.

---

# 16. Métricas estruturais de simplificação

O sistema também calcula sinais experimentais relacionados à redução de complexidade textual, como mudanças em:

- tamanho médio das frases;
- incidência de palavras mais longas;
- quantidade de termos potencialmente complexos.

Esses valores servem como **diagnóstico estrutural**.

Eles não demonstram, isoladamente:

- compreensão humana;
- qualidade científica;
- correção factual;
- adequação a uma pessoa específica;
- acessibilidade garantida para pessoas com baixo letramento.

A avaliação com leitores humanos continua necessária para sustentar alegações de compreensão real.

---

# 17. Modelos generativos

O revisor utiliza Gemini como família principal e Groq como fallback final.

A ordem operacional atual é:

```text
1. GEMINI_MODEL
2. GEMINI_FALLBACK_MODEL
3. GROQ_MODEL
```

Os valores padrão do projeto são configuráveis pelo `.env`.

Exemplo:

```env
GEMINI_MODEL=gemini-3.5-flash
GEMINI_FALLBACK_MODEL=gemini-3.6-flash
GROQ_MODEL=llama-3.3-70b-versatile
```

O painel registra qual modelo efetivamente respondeu em cada etapa.

Isso é importante porque um único rascunho pode usar modelos diferentes caso ocorra fallback.

Para um experimento comparativo, um rascunho que misturou modelos não deve ser rotulado como resultado puro de um único modelo.

---

# 18. Proveniência registrada no painel

Sempre que disponível, o revisor informa o modelo usado em cada etapa:

```text
Tradução-base
Ficha factual
Divulgação + resumo
Leitura facilitada
Checagem do núcleo
Reparo da leitura
Rechecagem da leitura
Auditoria de fidelidade
```

Essa rastreabilidade deve ser preservada nos testes do TCC.

---

# 19. Requisitos

Recomenda-se Python 3.10 ou superior.

Instalação básica das dependências:

```bash
python -m pip install -U streamlit python-dotenv requests google-genai groq deep-translator spacy pyphen sentence-transformers
```

Opcionalmente, instale um modelo de português do spaCy:

```bash
python -m spacy download pt_core_news_sm
```

O código tenta carregar, nesta ordem, modelos `lg`, `md` e `sm`. Se nenhum estiver instalado, ainda pode usar um pipeline básico em português, mas algumas tarefas linguísticas ficam menos robustas.

Na primeira utilização do Sentence Transformers, o modelo MiniLM pode precisar ser baixado, o que exige conexão com a internet.

---

# 20. Ambiente virtual recomendado

## Windows / PowerShell

Criar:

```powershell
python -m venv venv
```

Ativar:

```powershell
.\venv\Scripts\Activate.ps1
```

Instalar dependências:

```powershell
python -m pip install -U pip
python -m pip install -U streamlit python-dotenv requests google-genai groq deep-translator spacy pyphen sentence-transformers
```

## Linux/macOS

Criar:

```bash
python -m venv venv
```

Ativar:

```bash
source venv/bin/activate
```

Instalar:

```bash
python -m pip install -U pip
python -m pip install -U streamlit python-dotenv requests google-genai groq deep-translator spacy pyphen sentence-transformers
```

---

# 21. Configuração do `.env`

Crie um arquivo `.env` na raiz do projeto.

Exemplo seguro:

```env
# -------------------------------------------------
# COLETA
# -------------------------------------------------
USER_EMAIL=seu_email@exemplo.com

# Opcionais
NCBI_API_KEY=
SEMANTIC_SCHOLAR_KEY=

# Embase / Elsevier
EMBASE_API_KEY=
EMBASE_INSTTOKEN=
ATIVAR_EMBASE=1

# Enriquecimento bibliográfico
ATIVAR_ENRIQUECIMENTO=1

# -------------------------------------------------
# GERAÇÃO E AUDITORIA
# -------------------------------------------------
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
GEMINI_FALLBACK_MODEL=gemini-3.6-flash

GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile

# Tentativas para erros transitórios
LLM_TENTATIVAS_TRANSITORIAS=3

# -------------------------------------------------
# MINI-LM
# -------------------------------------------------
ATIVAR_MINILM=1
MINILM_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

## Segurança

Nunca envie o `.env` para o GitHub.

Adicione ao `.gitignore`:

```gitignore
.env
venv/
__pycache__/
*.pyc
```

Também não coloque chaves de API em:

- README;
- código-fonte;
- screenshots;
- TCC;
- relatórios públicos;
- arquivos de exemplo.

Se uma chave real já tiver sido exposta em arquivo compartilhado, histórico Git ou captura de tela, o procedimento correto é revogá-la e gerar outra.

---

# 22. Como iniciar a plataforma do zero

A ordem recomendada é:

```text
1. configurar ambiente e .env
2. executar coleta
3. abrir painel editorial
4. gerar rascunho
5. revisar e reavaliar
6. aprovar/publicar
7. abrir portal público
```

## Passo 1 — executar o coletor

```bash
python coletor_artigos.py
```

Confirme a criação/atualização de:

```text
artigos_coletados.json
```

## Passo 2 — limpar cache do Streamlit após atualizar o código

```bash
streamlit cache clear
```

## Passo 3 — abrir o painel editorial

```bash
python -m streamlit run revisor_jornal_ciencia.py
```

A barra lateral deve mostrar:

```text
Painel editorial simples
```

## Passo 4 — abrir o portal público

Em outro terminal, na pasta em que estão `index.html` e `noticias.json`:

```bash
python -m http.server 8000
```

Depois abra no navegador:

```text
http://localhost:8000/index.html
```

---

# 23. Como usar o painel editorial

O revisor organiza os artigos em quatro estados principais.

## 🟡 Pendente

Artigo coletado que ainda não possui rascunho editorial.

A ação principal é gerar o rascunho.

Durante a geração, o pipeline executa aproximadamente:

```text
abstract original
      ↓
tradução-base
      ↓
ficha de evidência
      ↓
plano de simplificação
      ↓
N1 + resumo técnico
      ↓
N2 independente
      ↓
checagem do N2
      ↓
reparo único, se necessário
      ↓
auditoria de fidelidade
```

## 🔵 Para aprovar

O rascunho já foi criado e aguarda revisão editorial.

Nesta etapa é possível editar:

- manchete;
- subtítulo;
- Divulgação científica;
- `O principal`;
- `O que o artigo fez`;
- `O que foi encontrado`;
- `O que ainda não sabemos`;
- Resumo científico em português.

### Botão “Salvar”

Salva as mudanças humanas sem executar novamente toda a auditoria.

### Botão “Salvar e reavaliar”

Salva as alterações e executa novamente as checagens aplicáveis e a auditoria sobre os textos editados.

Esse botão **não deve ser entendido como “regenerar o rascunho do zero”**. Isso evita sobrescrever silenciosamente a edição humana.

### Botão “Excluir rascunho”

Remove o rascunho e devolve o artigo ao estado pendente.

A tradução-base persistente pode continuar salva em `traducoes_base.json`. Assim, ao gerar novamente o mesmo abstract, o sistema tende a reutilizar a mesma tradução.

### Aprovação

Antes da publicação, o usuário precisa confirmar que revisou:

- Divulgação científica;
- os quatro blocos da Leitura Facilitada;
- Resumo científico em português.

Depois disso, o botão de aprovação/publicação fica disponível conforme as regras do painel.

Se a auditoria estiver bloqueando o rascunho, pode ser necessária uma justificativa textual explícita para publicação excepcional.

## 🟢 Publicado

O conteúdo está registrado em `noticias.json` e aparece no portal público.

O painel permite consultar as três formas de leitura e despublicar a matéria.

## 🔴 Rejeitado

O artigo não aparece no portal e fica fora da fila ativa de aprovação.

Pode ser reconsiderado posteriormente.

---

# 24. Arquivos de dados

## `artigos_coletados.json`

Contém os artigos encontrados e selecionados pelo coletor.

## `rascunhos.json`

Contém conteúdos gerados e ainda não publicados, além de dados de rastreabilidade, métricas e avaliação.

## `noticias.json`

É a fonte de dados do portal público. Um conteúdo só aparece no site quando está neste arquivo como publicação.

## `estado_editorial.json`

Mantém estados editoriais associados aos artigos.

## `historico_editorial.json`

Registra ações como geração, edição, reavaliação, publicação, rejeição e reconsideração.

## `traducoes_base.json`

Cache persistente das traduções-base. É especialmente importante para manter consistência entre regenerações do mesmo abstract.

---

# 25. Portal público

O portal foi pensado para permitir que um mesmo artigo seja lido em níveis diferentes.

Dependendo dos dados disponíveis, a interface pode apresentar:

- manchete;
- subtítulo;
- autores e ano;
- tema;
- acesso ao artigo original;
- Divulgação científica;
- Leitura Facilitada;
- Resumo científico em português;
- recursos de leitura em voz alta;
- detalhes técnicos ou rastreabilidade editorial quando configurados para exibição.

A Leitura Facilitada não substitui a Divulgação Científica. Ela é uma forma de leitura adicional com menor complexidade textual.

---

# 26. Reavaliação versus regeneração

Essa diferença é importante para os testes.

## Reavaliar

```text
texto atual editado pelo humano
          ↓
nova checagem/auditoria
```

O conteúdo não deve ser recriado indiscriminadamente.

## Regenerar

Para obter um novo N1/N2 a partir do prompt atual:

```text
excluir rascunho
      ↓
artigo volta a pendente
      ↓
gerar novo rascunho
```

Se a tradução-base do mesmo abstract já estiver em cache, ela pode ser reutilizada.

Isso é especialmente importante quando o prompt de simplificação é alterado e se deseja testar a nova configuração de forma limpa.

---

# 27. Reiniciar os dados para uma nova rodada experimental

Antes de apagar qualquer arquivo, faça uma cópia de segurança.

Para iniciar uma nova rodada mantendo apenas a configuração do sistema, normalmente é possível reiniciar os arquivos editoriais:

```powershell
Set-Content rascunhos.json "[]" -Encoding UTF8
Set-Content noticias.json "[]" -Encoding UTF8
Set-Content estado_editorial.json "{}" -Encoding UTF8
Set-Content historico_editorial.json "[]" -Encoding UTF8
```

Se também desejar refazer a coleta:

```powershell
Remove-Item artigos_coletados.json -ErrorAction SilentlyContinue
python coletor_artigos.py
```

### O que fazer com `traducoes_base.json`?

Para testes que desejam **manter a mesma tradução-base entre regenerações**, não apague esse arquivo.

Só reinicie o cache de traduções se a metodologia do experimento exigir deliberadamente produzir novas traduções. Nesse caso, isso deve ser documentado como alteração experimental.

---

# 28. Erros e problemas comuns

## Google Translate retorna erro 500/502/503/504

O sistema possui novas tentativas automáticas.

Se todas falharem:

- aguarde e tente gerar depois;
- verifique conexão;
- não substitua manualmente a etapa por uma tradução de LLM se estiver mantendo a metodologia descrita neste projeto.

## Gemini retorna erro transitório

O sistema tenta novamente e pode avançar para o segundo modelo Gemini.

Se ambos falharem, tenta Groq quando configurado.

## Groq retorna 429

O provedor atingiu limite temporário.

Quando a mensagem contém um intervalo de espera, o revisor registra esse período e tenta evitar novas chamadas inúteis durante a mesma sessão.

A solução normalmente é aguardar a liberação da cota ou revisar o plano/limites da API.

## Embase retorna 403

Isso normalmente indica problema de autorização/entitlement da API, e não necessariamente chave digitada incorretamente.

Verifique acesso institucional, VPN quando aplicável e autorização da Elsevier para uso programático.

## MiniLM não carrega

O painel foi projetado para continuar funcional quando a métrica auxiliar não puder ser carregada.

Nesse caso:

- a geração e o fluxo editorial podem continuar;
- a recuperação semântica MiniLM ficará indisponível;
- registre essa diferença se estiver coletando resultados experimentais.

## Artigo publicado não aparece no portal

Confirme:

1. se o artigo foi realmente publicado no painel;
2. se `noticias.json` foi atualizado;
3. se o servidor HTTP está sendo executado na pasta correta;
4. se o navegador não está exibindo uma cópia antiga em cache;
5. se `index.html` e `noticias.json` estão no mesmo diretório servido.

## Rascunho antigo não muda após atualizar o código

Rascunhos já salvos não são necessariamente regenerados após uma alteração no prompt.

Para testar integralmente uma nova configuração de geração:

```text
Excluir rascunho → Gerar rascunho novamente
```

---

# 29. O que a plataforma NÃO afirma

Para evitar interpretações metodológicas incorretas, o Jornal Cienc.IA não deve afirmar que:

- o MiniLM mede “verdade”;
- uma similaridade de embeddings é porcentagem de fidelidade;
- a FI é uma métrica clínica validada;
- frases curtas provam compreensão;
- o N2 é automaticamente compreensível por toda pessoa com baixo letramento;
- a prioridade editorial mede qualidade científica;
- a auditoria por LLM elimina a necessidade de revisão humana;
- o conteúdo publicado substitui orientação profissional em saúde.

---

# 30. Limitações atuais

A implementação possui limitações importantes que devem ser descritas no TCC e consideradas nos experimentos:

- a geração editorial atual está centrada no **abstract**, não em uma interpretação sistemática do artigo completo;
- o coletor continua baseado em **temas de busca**;
- disponibilidade de um DOI não significa automaticamente texto completo aberto;
- metadados de desenho de estudo podem estar incompletos ou classificados de forma diferente entre bases;
- a ficha estruturada é produzida por LLM e pode conter erros;
- a própria auditoria automática pode produzir falsos positivos ou falsos negativos;
- métricas de similaridade semântica não substituem avaliação factual;
- diagnósticos de complexidade textual não substituem testes com leitores;
- APIs externas estão sujeitas a indisponibilidade, alteração de limites e rate limiting;
- modelos generativos podem mudar de comportamento após atualizações realizadas pelos provedores.

Por isso, os resultados finais devem combinar análise automatizada com revisão humana documentada.

---

# 31. Reprodutibilidade dos testes

Antes de iniciar a coleta oficial de resultados do TCC, recomenda-se congelar a configuração metodológica.

Registre pelo menos:

```text
identificador do código do coletor (por exemplo, commit do Git)
identificador do código do revisor (por exemplo, commit do Git)
modelo Gemini principal
modelo Gemini fallback
modelo Groq
modelo MiniLM
ATIVAR_MINILM
parâmetros do N2
regra de uma rodada de reparo
definição e fórmula de FI utilizadas
limiar da prioridade editorial
fontes de descoberta utilizadas
estado do Embase
```

Depois de iniciar a rodada experimental, alterações relevantes no pipeline devem ser registradas como uma nova configuração experimental e não devem ser misturadas silenciosamente aos resultados anteriores.

Também registre a proveniência efetiva de cada rascunho. Se houve fallback entre modelos, isso deve aparecer na análise experimental.

---

# 32. Fluxo recomendado para avaliação de cada artigo

Para cada artigo selecionado:

```text
1. conferir título, autores e fonte
2. conferir abstract original
3. conferir tradução-base
4. conferir ficha estruturada
5. ler Divulgação Científica
6. ler Leitura Facilitada
7. ler Resumo Científico em português
8. verificar números e conclusões contra a fonte
9. verificar limitações e incertezas
10. consultar rastreabilidade MiniLM
11. consultar FI e motivo do status
12. editar problemas encontrados
13. salvar e reavaliar
14. fazer leitura humana final
15. aprovar, rejeitar ou manter pendente
```

A ordem reforça que a pontuação automática não substitui a conferência do conteúdo.

---

# 33. Fluxo rápido de uso

Depois que o ambiente estiver configurado:

```bash
# 1. Coletar artigos
python coletor_artigos.py

# 2. Limpar cache após atualizar o código
streamlit cache clear

# 3. Abrir painel editorial
python -m streamlit run revisor_jornal_ciencia.py
```

Em outro terminal:

```bash
# 4. Servir portal público
python -m http.server 8000
```

Acesse:

```text
Painel editorial: endereço mostrado pelo Streamlit
Portal público: http://localhost:8000/index.html
```

---

# 34. Resumo da arquitetura atual

```text
┌────────────────────────────────────────────┐
│ PubMed + Europe PMC + Embase opcional      │
│         descoberta biomédica               │
└──────────────────────┬─────────────────────┘
                       ↓
              deduplicação de registros
                       ↓
┌────────────────────────────────────────────┐
│ Semantic Scholar + OpenAlex + Crossref     │
│          enriquecimento apenas             │
└──────────────────────┬─────────────────────┘
                       ↓
            prioridade editorial ≥ 60
                       ↓
              artigos_coletados.json
                       ↓
┌────────────────────────────────────────────┐
│             Painel Streamlit               │
│                                            │
│  abstract original                        │
│       ↓                                    │
│  tradução-base fixa                       │
│       ↓                                    │
│  ficha estruturada                        │
│       ↓                                    │
│  N1 + resumo técnico                      │
│       ↓                                    │
│  N2 independente                          │
│       ↓                                    │
│  checagem + no máximo 1 reparo            │
│       ↓                                    │
│  MiniLM + Fidelidade Intelectual           │
│       ↓                                    │
│  REVISÃO HUMANA                            │
└──────────────────────┬─────────────────────┘
                       ↓
                  noticias.json
                       ↓
┌────────────────────────────────────────────┐
│            Jornal Cienc.IA                 │
│                                            │
│   Divulgação científica                   │
│   Leitura facilitada                      │
│   Resumo científico em português          │
└────────────────────────────────────────────┘
```

---

# 35. Frase metodológica central

> **No Jornal Cienc.IA, simplificar não significa dizer menos; significa exigir menos esforço linguístico para compreender aquilo que continua cientificamente necessário.**

---

## Estado atual do projeto

Este README descreve o fluxo implementado pelo **coletor biomédico** e pelo **painel editorial**, incluindo a tradução-base fixa, Leitura Facilitada independente, checagem do núcleo informacional, reparo controlado, recuperação semântica bilíngue com MiniLM, auditoria de Fidelidade Intelectual e revisão humana antes da publicação.

Ao alterar componentes metodologicamente relevantes, atualize também este README e registre claramente as mudanças realizadas para manter a reprodutibilidade do TCC.
