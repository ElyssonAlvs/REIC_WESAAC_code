# ADR 0003: Fábrica Híbrida de Provedores de LLM (Groq Cloud + Ollama Local)

- **Status:** Aceito
- **Data:** 2026-10-02
- **Decisores:** Elysson Alves de Lacerda (Tech Lead), Antigravity (Tech Manager)
- **Contexto Técnico:** Conectividade de LLMs para inferência dos agentes.

---

## Contexto e Forças Impulsionadoras

O projeto necessita de inferência rápida e confiável para tarefas de raciocínio e geração estruturada de JSON. Três restrições operacionais foram colocadas pelo Tech Lead:
1. Não incorrer em custos financeiros com APIs comerciais pagas no momento.
2. Evitar limites de quota excessivamente restritivos (como os 50 req/dia do OpenRouter free tier sem cartão).
3. Garantir suporte a execução 100% offline (on-premise/local) com modelos já instalados (Llama 3 8B via Ollama).

---

## Decisão

Implementamos o padrão **Factory Method** em `sprint_mas/llm_factory.py`, desacoplando completamente os agentes da escolha do provedor:

1. **Groq (`ChatGroq`) como Provedor Principal:**
   - Modelo: `llama-3.1-8b-instant`.
   - Vantagens: Inferência em LPUs ultrarrápidas, taxa de ~14.400 requisições/dia gratuitas, suporte estável a saídas JSON estruturadas.
2. **Ollama (`ChatOllama`) como Fallback Local:**
   - Modelo: `llama3:latest` (já presente na máquina do Tech Lead).
   - Vantagens: Independência de internet, zero custos, suporte nativo a `with_structured_output`.
3. **Seleção Declarativa:** O provedor é definido via variável de ambiente `PROVIDER=groq` ou `PROVIDER=ollama`.

---

## Consequências

### Positivas
- **Flexibilidade Total:** Alternância entre nuvem gratuita e ambiente local sem tocar em nenhuma linha de código dos agentes.
- **Testes Isolados:** Mocks da fábrica permitem testar toda a lógica da aplicação sem fazer chamadas de rede no CI/CD.

### Negativas / Mitigações
- Requer gerenciamento de variáveis de ambiente via `.env` (mitigado pelo `.env.example`).
