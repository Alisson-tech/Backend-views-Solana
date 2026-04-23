# Planejamento de Autenticação (Simple API Key)

Como arquiteto do projeto, analisei a estrutura atual (FastAPI + Pydantic Settings) e proponho a seguinte abordagem simples, mas robusta e modular, para adicionar uma proteção básica via API Key fixa. Essa abordagem respeita a arquitetura de injeção de dependências do FastAPI.

## 1. Configuração da API Key (`app/core/config.py`)
Adicionar a chave secreta às configurações da aplicação para que seja carregada via variáveis de ambiente (arquivo `.env`), mantendo a segurança e aderência ao módulo `pydantic-settings` já utilizado no projeto.

- **Ação:** Incluir o atributo `APP_API_KEY: str` na classe `Settings` em `app/core/config.py`.

## 2. Dependência de Segurança (`app/api/deps.py`)
Criar um novo arquivo focado em dependências da API. Isso mantém o código limpo, isola o acoplamento e facilita reusabilidade.

- **Ação:** Criar o arquivo `app/api/deps.py`.
- **Implementação:** 
  Utilizar `APIKeyHeader` do módulo `fastapi.security` para definir a captura da chave via cabeçalho (exemplo: `X-API-Key`).
  Criar uma função injetável `get_api_key(api_key: str = Depends(api_key_header))` que compara a chave fornecida na requisição com a configurada em `settings.APP_API_KEY`. Se forem diferentes, levanta a exceção `HTTPException(status_code=401, detail="Invalid API Key")`.

## 3. Aplicação da Segurança (`app/api/endpoints.py`)
Proteger as rotas de negócio, permitindo que as rotas de infra (como `/health` no `main.py`) fiquem públicas se for o caso.

- **Ação:** Adicionar a dependência de segurança diretamente no Router.
- **Implementação:** Alterar a inicialização do router de análise para exigir a key em todas as suas rotas:
  `router = APIRouter(prefix="/api/v1", tags=["analysis"], dependencies=[Depends(get_api_key)])`

## Benefícios Desta Arquitetura:
- **Separação de Preocupações:** A lógica de validação do token não "suja" o código de rotas ou serviços/orquestradores.
- **"The FastAPI Way":** Aproveita ao máximo a documentação interativa (Swagger UI) já que a classe `APIKeyHeader` se integra automaticamente à documentação do OpenAPI.
- **Simplicidade com Escalabilidade:** Apesar de ser uma API key fixa (`fixed token`), a estrutura com `deps.py` está pronta para futura evolução (ex: múltiplas chaves em banco de dados ou integração com JWT), sem grande refatoração na camada da controladora (`endpoints.py`).
