# 📰 Jornal Cienc.IA

**Ciência em saúde, clara e fiel à evidência.**

Plataforma experimental de divulgação científica em saúde desenvolvida no contexto de Trabalho de Conclusão de Curso (TCC). O sistema coleta e prioriza literatura biomédica, produz diferentes formas de leitura em português, recupera evidências relacionadas às afirmações geradas, realiza auditoria de Fidelidade Intelectual e mantém a decisão final de publicação sob responsabilidade humana.

> Estado documentado: setembro de 2026.

---

## 1. Objetivo

O Jornal Cienc.IA investiga como modelos de linguagem e técnicas auxiliares de processamento de linguagem podem apoiar a divulgação científica em saúde para leitores com diferentes necessidades de leitura, sem abandonar a rastreabilidade em relação à evidência utilizada como fonte.

A implementação atual trabalha principalmente com **abstracts científicos**. O sistema não deve ser apresentado como ferramenta de diagnóstico, recomendação clínica, verificador universal de verdade ou substituto da leitura crítica do artigo original.

Princípio central:

> **Simplificar não significa dizer menos; significa exigir menos esforço linguístico para compreender aquilo que continua cientificamente necessário.**

---

## 2. Arquitetura geral

```text
PubMed + OpenAlex + Embase opcional
              ↓
      deduplicação e triagem
              ↓
     prioridade editorial ≥ 60
              ↓
      artigos_coletados.json
              ↓
       Painel Streamlit
              ↓
       tradução-base
 Google Translate → OPUS-MT fallback
              ↓
 Ficha Estruturada de Evidência
              ↓
      plano de simplificação
              ↓
 ┌────────────┴────────────┐
 ↓                         ↓
Divulgação científica   Leitura Facilitada
       (N1)                   (N2)
 └────────────┬────────────┘
              ↓
 sentenças / afirmações
              ↓
 MiniLM recupera evidências candidatas
              ↓
 auditoria de Fidelidade Intelectual
              ↓
 sustentação + cobertura + incerteza
              ↓
        REVISÃO HUMANA
              ↓
        noticias.json
              ↓
       Jornal Cienc.IA
```

A revisão humana é obrigatória. Uma boa pontuação automática não autoriza publicação por si só.

---

## 3. Componentes principais

### 3.1 Coletor biomédico

Arquivo:

```text
coletor_artigos.py
```

Responsável por:

- buscar artigos;
- normalizar registros;
- deduplicar;
- classificar o desenho do estudo a partir dos metadados disponíveis;
- calcular prioridade editorial;
- produzir `artigos_coletados.json`.

### 3.2 Painel editorial

Arquivo:

```text
revisor_jornal_ciencia.py
```

Aplicação Streamlit utilizada para:

- visualizar a fila editorial;
- gerar rascunhos;
- editar manchete e subtítulo;
- editar Divulgação Científica e Leitura Facilitada;
- consultar a tradução-base;
- consultar a Ficha Estruturada de Evidência;
- inspecionar checagens de simplificação;
- consultar evidências recuperadas por MiniLM;
- consultar a auditoria de Fidelidade Intelectual;
- salvar e reavaliar;
- aprovar, publicar, rejeitar ou despublicar.

### 3.3 Portal público

Arquivo principal:

```text
index.html
```

O portal lê:

```text
noticias.json
```

Somente os conteúdos publicados no painel são exibidos no portal.

---

# 4. Coleta biomédica

## 4.1 Fontes atuais

A versão atual do coletor utiliza como fontes de descoberta:

- **PubMed**;
- **OpenAlex**;
- **Embase**, quando houver credenciais e entitlement institucional.

Nesta versão, **Semantic Scholar, Crossref e Europe PMC não são consultados**.

O Embase é opcional. Na ausência de chave ou autorização institucional, a coleta continua com PubMed e OpenAlex.

## 4.2 Variáveis do Embase

```env
ATIVAR_EMBASE=1
EMBASE_API_KEY=
EMBASE_INSTTOKEN=
```

`EMBASE_INSTTOKEN` é opcional e só deve ser utilizado quando fornecido/autorizado pela instituição ou pela Elsevier.

## 4.3 Deduplicação

O coletor tenta reconhecer o mesmo artigo encontrado em fontes diferentes.

Prioridade:

1. DOI normalizado;
2. quando não há DOI, título normalizado.

As fontes em que o artigo foi localizado permanecem registradas em `fontes_encontradas`.

## 4.4 Busca por temas

O coletor utiliza uma lista de temas padrão, mas também aceita temas informados pela linha de comando.

Exemplo:

```bash
python coletor_artigos.py --temas "nutrition diet health outcomes" "vaccine safety adverse effects"
```

O parâmetro `--limite-busca` controla quantos registros cada fonte pode consultar antes da triagem. Ele **não define um máximo de artigos selecionados**.

---

# 5. Prioridade editorial

A prioridade é um sinal operacional de **0 a 100**. Ela não representa qualidade científica, certeza da evidência ou nível OCEBM automático.

O total combina:

```text
P = D + A + B + O + R
```

onde:

- `D` = peso do desenho do estudo;
- `A` = atualidade;
- `B` = impacto bibliométrico;
- `O` = disponibilidade de acesso;
- `R` = relevância/posição retornada pela fonte.

## 5.1 Atualidade

```text
A = max(0, 20 - 1,5 × idade)
```

## 5.2 Impacto bibliométrico

```text
B = min(20,
        ln(1 + citações_totais) × 3,2
        +
        ln(1 + citações_influentes) × 5,0)
```

## 5.3 Acesso

```text
PDF aberto identificado              → 10 pontos
texto completo aberto identificado   →  8 pontos
DOI sem acesso aberto confirmado     →  2 pontos
sem acesso identificado              →  0 pontos
```

## 5.4 Relevância na fonte

```text
R = max(0, 10 - 0,35 × min(rank, 20))
```

## 5.5 Limiar

```python
MIN_PRIORIDADE_EDITORIAL = 60.0
```

Todos os artigos elegíveis com pontuação igual ou superior a 60 podem entrar na fila editorial.

---

# 6. Tradução-base

Antes da geração dos textos em português, o revisor cria uma tradução-base do abstract.

## 6.1 Estratégia atual

O método principal continua sendo:

```text
Google Translate via deep-translator
```

Se o Google Translate permanecer indisponível após as tentativas previstas, o sistema utiliza como **fallback técnico**:

```text
Helsinki-NLP/opus-mt-tc-big-en-pt
```

O OPUS-MT é um modelo Marian NMT específico para tradução inglês → português. Ele não substitui os modelos generativos do pipeline e não é usado como LLM editorial.

Gemini e Groq **não são usados como tradutores**.

## 6.2 Tentativas do Google

O Google mantém quatro tentativas:

```text
imediata → +3 s → +8 s → +20 s
```

As chamadas são serializadas no processo para reduzir rajadas.

Valores padrão:

```env
GOOGLE_TRADUCAO_MAX_CHARS=3800
GOOGLE_TRADUCAO_INTERVALO_SEGUNDOS=1.1
```

Textos maiores que o limite são divididos em blocos.

## 6.3 Regra de não misturar tradutores

Um mesmo abstract não é traduzido parcialmente pelo Google e parcialmente pelo OPUS-MT.

Se qualquer bloco do Google falhar definitivamente, a tradução parcial do Google é descartada e o OPUS-MT traduz o abstract completo.

## 6.4 Fallback OPUS-MT

Configuração padrão:

```env
OPUS_MT_MODEL=Helsinki-NLP/opus-mt-tc-big-en-pt
OPUS_MT_MAX_INPUT_TOKENS=430
OPUS_MT_BATCH_SIZE=4
```

O modelo é carregado apenas quando o fallback é necessário.

## 6.5 Cache persistente

As traduções-base são armazenadas em:

```text
traducoes_base.json
```

O registro inclui o tradutor efetivamente utilizado e, quando aplicável, o motivo do fallback.

Caches válidos produzidos pelo Google continuam reutilizáveis. Uma tradução OPUS-MT só é reaproveitada pela estratégia atual quando estiver registrada explicitamente como **fallback do Google**.

---

# 7. Ficha Estruturada de Evidência

Depois da tradução-base, o sistema extrai uma representação estruturada do conteúdo científico.

A ficha pode registrar:

```text
tipo do estudo
objetivo/pergunta
contexto
população ou amostra
intervenção, exposição ou condição
comparador, quando aplicável
desfechos
resultados principais
números importantes
limitações
incertezas e ressalvas
termos técnicos essenciais
o que não pode ser concluído
informações ausentes
```

A estrutura é adaptativa ao desenho do estudo. **PICO é utilizado quando metodologicamente compatível**, e não imposto a todos os artigos.

A metodologia é inspirada por princípios de avaliação apresentados em trabalhos como **FactPICO** e **FaReBio**, sem afirmar que o Jornal Cienc.IA implementa integralmente esses benchmarks.

---

# 8. Formas de leitura

## 8.1 Divulgação Científica — N1

Voltada ao público geral adulto.

Objetivos:

- linguagem jornalística clara;
- apresentar cedo o achado principal;
- explicar o que o estudo fez;
- preservar números relevantes;
- preservar limitações;
- evitar sensacionalismo;
- não inventar recomendações clínicas;
- não converter associação em causalidade.

## 8.2 Leitura Facilitada — N2

Voltada a leitores que se beneficiam de menor complexidade lexical e menor carga de inferência.

O N2 é gerado de forma independente a partir da fonte, tradução-base, ficha e plano de simplificação.

Estrutura pública:

```text
O principal
O que o artigo fez
O que foi encontrado
O que ainda não sabemos
```

Uma informação cientificamente necessária não deve ser retirada apenas por ser difícil. Quando possível, ela deve ser explicada.

## 8.3 Resumo científico em português

É a tradução-base técnica usada como forma de leitura mais próxima do abstract original.

Deve preservar métodos, população/amostra, números, resultados, qualificadores, limitações e grau de certeza.

---

# 9. Plano de simplificação e NCL-IDF

O sistema utiliza um plano lexical auxiliar baseado em recorrência, IDF e relevância científica:

```text
NCL 0 → manter
NCL 1 → explicar/substituir quando possível
NCL 2 → substituir quando não for cientificamente essencial
```

O objetivo é apoiar a simplificação lexical sem remover termos científicos necessários.

Métricas estruturais de simplificação são diagnósticas e **não comprovam compreensão humana**.

---

# 10. MiniLM e recuperação de evidências

Modelo padrão:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

O MiniLM é usado como mecanismo auxiliar de **recuperação de evidências candidatas**.

Seu papel é localizar, na fonte, trechos semanticamente relacionados a cada afirmação gerada.

```text
afirmação gerada
      ↓
MiniLM
      ↓
top-k evidências candidatas
      ↓
auditoria factual
```

Uma similaridade vetorial de `0,82` não significa “82% fiel”.

---

# 11. Checagem da Leitura Facilitada

Antes da auditoria final, o N2 passa por checagens relacionadas a:

- fatos obrigatórios;
- números relevantes;
- possíveis omissões;
- termos técnicos;
- frases longas;
- frases com múltiplas ideias;
- ambiguidades;
- complexidade desnecessária.

Quando necessário, o sistema pode executar **uma rodada controlada de reparo** e reavaliar o resultado.

---

# 12. Fidelidade Intelectual

A plataforma utiliza a medida operacional:

```text
FI = 0,50 × S
   + 0,25 × C
   + 0,25 × I
```

onde:

- `S` = Sustentação;
- `C` = Cobertura;
- `I` = Preservação da Incerteza.

## 12.1 Sustentação

Verifica se as afirmações geradas possuem suporte na fonte.

```text
sustentada
parcialmente sustentada
não sustentada
```

## 12.2 Cobertura

Verifica se os elementos essenciais da Ficha Estruturada de Evidência permaneceram no texto.

## 12.3 Preservação da incerteza

Associação não deve virar causalidade, hipótese não deve virar fato e evidência limitada não deve virar certeza.

## 12.4 Informações adicionais

Explicações acrescentadas durante a simplificação também são tratadas como afirmações verificáveis.

## 12.5 Interpretação

A FI é uma **medida operacional do projeto**, não uma métrica clínica universal validada.

A decisão final continua sendo humana.

---

# 13. Modelos generativos

Configuração padrão atual:

```env
GEMINI_MODEL=gemini-3.5-flash
GEMINI_FALLBACK_MODEL=gemini-3.6-flash
GROQ_MODEL=openai/gpt-oss-120b
```

Papel geral:

```text
Gemini
  → simplificação editorial e reparos

Groq / modelo configurado
  → ficha factual, checagens e auditoria de fidelidade
```

O painel registra o modelo efetivamente utilizado em cada etapa.

---

# 14. Proveniência

Sempre que disponível, o revisor registra:

```text
tradutor efetivo
uso ou não de fallback de tradução
modelo da ficha factual
modelo da simplificação
modelo de checagem
modelo de reparo
modelo da auditoria
modelo MiniLM
evidências candidatas
métricas estruturais
Fidelidade Intelectual
ações editoriais humanas
```

---

# 15. Requisitos

Recomenda-se Python 3.10 ou superior.

```bash
python -m pip install -U streamlit python-dotenv requests google-genai groq deep-translator spacy pyphen sentence-transformers transformers sentencepiece torch
```

Opcionalmente:

```bash
python -m spacy download pt_core_news_sm
```

Na primeira utilização, MiniLM e OPUS-MT podem precisar baixar seus pesos.

---

# 16. Ambiente virtual

## Windows / PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -U streamlit python-dotenv requests google-genai groq deep-translator spacy pyphen sentence-transformers transformers sentencepiece torch
```

## Linux/macOS

```bash
python -m venv venv
source venv/bin/activate
python -m pip install -U pip
python -m pip install -U streamlit python-dotenv requests google-genai groq deep-translator spacy pyphen sentence-transformers transformers sentencepiece torch
```

---

# 17. Configuração do `.env`

```env
# COLETA
USER_EMAIL=seu_email@exemplo.com
NCBI_API_KEY=

ATIVAR_EMBASE=1
EMBASE_API_KEY=
EMBASE_INSTTOKEN=

# GERAÇÃO / AUDITORIA
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
GEMINI_FALLBACK_MODEL=gemini-3.6-flash

GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b

LLM_TENTATIVAS_TRANSITORIAS=4
PIPELINE_TENTATIVAS_ETAPA=4

# TRADUÇÃO
GOOGLE_TRADUCAO_MAX_CHARS=3800
GOOGLE_TRADUCAO_INTERVALO_SEGUNDOS=1.1

OPUS_MT_MODEL=Helsinki-NLP/opus-mt-tc-big-en-pt
OPUS_MT_MAX_INPUT_TOKENS=430
OPUS_MT_BATCH_SIZE=4

# MINI-LM
ATIVAR_MINILM=1
MINILM_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Nunca envie `.env` para o GitHub.

`.gitignore` recomendado:

```gitignore
.env
venv/
.venv/
__pycache__/
*.pyc
.cache/
```

---

# 18. Estrutura recomendada

```text
jornal-ciencia/
├── coletor_artigos.py
├── revisor_jornal_ciencia.py
├── index.html
├── styles.css
├── app.js
├── README.md
├── .env
├── .gitignore
├── artigos_coletados.json
├── noticias.json
├── rascunhos.json
├── estado_editorial.json
├── historico_editorial.json
└── traducoes_base.json
```

---

# 19. Execução

## Coletar

```bash
python coletor_artigos.py
```

## Limpar cache do Streamlit depois de atualizar o código

```bash
streamlit cache clear
```

## Abrir painel

```bash
python -m streamlit run revisor_jornal_ciencia.py
```

## Servir portal

```bash
python -m http.server 8000
```

Portal:

```text
http://localhost:8000/index.html
```

---

# 20. Regeneração e reavaliação

## Reavaliar

```text
texto atual
   ↓
checagem + auditoria
```

## Regenerar

```text
excluir rascunho
      ↓
artigo volta a pendente
      ↓
gerar novo rascunho
```

A tradução-base compatível pode permanecer em cache.

---

# 21. Arquivos de dados

- `artigos_coletados.json`: resultado da coleta e triagem.
- `rascunhos.json`: rascunhos com rastreabilidade e avaliação.
- `noticias.json`: conteúdos publicados.
- `estado_editorial.json`: estado de cada artigo.
- `historico_editorial.json`: ações editoriais.
- `traducoes_base.json`: tradução-base e proveniência.

---

# 22. Erros comuns

## Google Translate retorna `TooManyRequests`

O sistema executa as tentativas previstas. Persistindo a indisponibilidade, para fonte compatível, o OPUS-MT local é acionado automaticamente.

Gemini e Groq não são utilizados como tradutores.

## OPUS-MT não carrega

```bash
python -m pip install -U transformers sentencepiece torch
```

## Gemini retorna erro transitório

O pipeline repete a etapa conforme a configuração e pode usar o Gemini fallback.

## Groq retorna `429`

O provedor atingiu limite temporário. A ocorrência deve permanecer registrada na proveniência quando afetar o rascunho.

## MiniLM não carrega

A recuperação semântica pode ficar indisponível. A diferença deve ser registrada nos testes experimentais.

---

# 23. Reprodutibilidade

Antes da coleta oficial de resultados, registre:

```text
commit Git do coletor
commit Git do revisor
fontes de coleta ativas
limiar de prioridade editorial
tradutor principal
fallback de tradução
modelo Gemini principal
modelo Gemini fallback
modelo Groq
modelo MiniLM
parâmetros NCL-IDF
parâmetros da Leitura Facilitada
regra de reparo
fórmula da Fidelidade Intelectual
```

Se o Google falhar e um artigo utilizar OPUS-MT, isso deve constar na proveniência e na análise experimental.

Alterações metodologicamente relevantes depois do início da coleta oficial devem gerar uma nova configuração experimental.

---

# 24. O que a plataforma não afirma

O Jornal Cienc.IA não afirma que:

- MiniLM mede verdade;
- similaridade vetorial é porcentagem de fidelidade;
- Fidelidade Intelectual é uma métrica clínica validada;
- frases curtas provam compreensão;
- N2 é automaticamente compreensível por todas as pessoas;
- prioridade editorial equivale à qualidade científica;
- auditoria automática elimina revisão humana;
- conteúdo publicado substitui orientação profissional em saúde.

---

# 25. Limitações atuais

- geração editorial centrada principalmente no abstract;
- coleta orientada por temas;
- Embase depende de autorização;
- APIs externas podem sofrer rate limit;
- Google Translate via `deep-translator` depende de serviço externo;
- OPUS-MT atual funciona como fallback inglês → português;
- modelos locais exigem download inicial e recursos computacionais;
- metadados de desenho do estudo podem ser incompletos;
- ficha estruturada e auditoria automática podem errar;
- similaridade semântica não substitui verificação factual;
- métricas de simplificação não substituem avaliação com leitores;
- comportamento de APIs e modelos pode mudar com atualizações dos provedores.

---

# 26. Estado atual

```text
PubMed + OpenAlex + Embase opcional
        ↓
prioridade editorial operacional
        ↓
Google Translate
        ↓ se indisponível
OPUS-MT local como fallback técnico
        ↓
Ficha Estruturada de Evidência
        ↓
Divulgação Científica + Leitura Facilitada
        ↓
checagem / reparo controlado
        ↓
MiniLM para recuperação de evidências
        ↓
Fidelidade Intelectual
        ↓
revisão humana obrigatória
        ↓
publicação
```

A metodologia separa explicitamente tradução, geração editorial, recuperação de evidências, julgamento de fidelidade e decisão editorial humana.
