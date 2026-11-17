# Warumby Properties — preparação Supabase + Vercel

A v0.3.4 usa a mesma base de código tanto localmente quanto na nuvem. A Vercel reconhece Django diretamente; por isso não é necessário criar uma adaptação em `/api` nem um `vercel.json` apenas para rotear o WSGI.

## 1. Antes de migrar

1. Execute `fazer_backup.bat`.
2. Execute `exportar_dados_migracao.bat`.
3. Confirme que existe `backups/migracao_dados.json`.
4. Faça também uma cópia da pasta `media`.
5. Execute `atualizar.bat` antes da exportação final; ele gera/atualiza `core/migrations`. Depois execute `preparar_deploy.bat`. Ao enviar o projeto ao Git/Vercel, inclua a pasta `core/migrations` no repositório.

Não apague o `db.sqlite3` até validar o site em produção.

## 2. Supabase — banco PostgreSQL

Crie um projeto no Supabase. No painel do projeto, abra **Connect** e copie a string do **Transaction pooler** para uso na Vercel. Ela normalmente usa a porta `6543`.

A aplicação espera essa string em `DATABASE_URL`. Em Transaction Pooler ela desativa prepared statements e cursores server-side, pois esses recursos dependem da sessão de conexão.

## 3. Supabase — arquivos privados

Crie um bucket privado, por exemplo `warumby-private`.

Em Storage > Configuration > S3:

1. habilite o protocolo S3;
2. gere Access Key ID e Secret Access Key;
3. copie endpoint e região;
4. nunca coloque essas chaves no frontend ou em JavaScript.

As chaves S3 são usadas somente pelo Django no servidor. Os documentos continuam sendo entregues pelas rotas protegidas do Warumby Properties.

## 4. Variáveis necessárias

Veja `.env.example`. Na Vercel, configure pelo menos: `GESTAO_SECRET_KEY` / `DATABASE_URL` e variáveis do Storage. Segredos não devem ser publicados no GitHub.