# Warumby Properties

Sistema web de gestão de imóveis desenvolvido para centralizar a administração de prédios, apartamentos, moradores, pagamentos, despesas, documentos e relatórios financeiros.

**Versão atual:** v0.3.4.3  
**Aplicação online:** https://warumby-properties.vercel.app/

## Objetivo

O projeto nasceu da necessidade de substituir controles dispersos por uma aplicação única, acessível por computador e celular, com diferentes níveis de acesso para Proprietário, Administradores e Moradores.

## Principais funcionalidades

- Cadastro e gestão de prédios e apartamentos.
- Controle de apartamentos ocupados e vagos.
- Cadastro de moradores, responsáveis e moradores filiais.
- Perfis com permissões diferentes: Proprietário, Administrador e Morador.
- Controle de ocupações e histórico de responsáveis.
- Pagamentos de aluguel por competência, incluindo pagamentos parciais, atrasos, créditos e excedentes.
- Geração de recibos e comprovantes em PDF.
- Central de Contas para BRK, Equatorial, IPTU e outros serviços.
- Registro de despesas com competência, valor pago, data e comprovante opcional.
- Relatórios financeiros por período, prédio ou apartamento.
- Cálculo de receita, despesas e resultado líquido.
- Comprovante consolidado de múltiplos meses para um apartamento.
- Solicitações de manutenção e comunicados.
- Armazenamento privado de documentos e comprovantes.
- Anonimização de ex-moradores sem apagar o histórico financeiro necessário aos relatórios.

## Tecnologias

- **Python / Django 5.2** — backend, regras de negócio, autenticação e interface web.
- **PostgreSQL / Supabase** — banco de dados em produção.
- **Supabase Storage** — armazenamento privado de documentos e comprovantes.
- **Vercel** — hospedagem e execução da aplicação.
- **ReportLab** — geração de documentos PDF.
- **WhiteNoise** — entrega dos arquivos estáticos.

## APIs e integrações

A aplicação utiliza a API do **Supabase Storage** para armazenamento de arquivos privados. Os dados relacionais são acessados pelo backend Django diretamente no PostgreSQL do Supabase através de `psycopg` e do pooler de conexões.

BRK e Equatorial são atualmente integrados por links para seus portais; o sistema não utiliza API oficial dessas concessionárias.

## Segurança

- Senhas armazenadas com o mecanismo de hashing do Django.
- Arquivos privados armazenados no Supabase Storage e acessados por URLs assinadas temporárias.
- Row Level Security (RLS) habilitado nas tabelas públicas do Supabase.
- Acesso direto das roles `anon` e `authenticated` às tabelas Django revogado.
- Segredos e strings de conexão são fornecidos apenas por variáveis de ambiente e não fazem parte do repositório.
- `.env`, banco SQLite local, mídia, backups e arquivos temporários são ignorados pelo Git.

## Perfis de acesso

### Proprietário
Controle completo do sistema, incluindo imóveis, usuários, pagamentos, despesas, relatórios e permissões.

### Administrador
Pode ser limitado a prédios específicos e gerencia apenas os imóveis autorizados.

### Morador
Visualiza somente sua residência e recursos relacionados, como pagamentos, recibos, comunicados e manutenção.

## Executando localmente

No Windows, a forma mais simples é executar:

```text
instalar.bat
```

Depois crie o superusuário solicitado pela instalação e execute:

```text
iniciar_servidor.bat
```

Também é possível usar os comandos Django tradicionais com um ambiente virtual Python.

## Variáveis de ambiente

Use `.env.example` somente como referência. Nunca publique credenciais reais no GitHub.

Em produção são necessárias variáveis para chave secreta do Django, conexão PostgreSQL, domínio permitido e Supabase Storage.

## Testes

A versão v0.3.4.3 passou por testes automatizados das principais regras de negócio, incluindo pagamentos parciais, créditos, promoção de Administrador, encerramento de ocupação sem pendência fantasma, anonimização de ex-morador, despesas e PDFs.

## Estado atual

O sistema está publicado e funcional em produção, utilizando Vercel + Supabase, e continua em evolução.
