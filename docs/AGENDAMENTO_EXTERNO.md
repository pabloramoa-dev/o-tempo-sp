# Agendamento externo para @otemposp

O schedule do GitHub Actions pode atrasar horas e perder a janela de publicação. O arquivo `.github/workflows/reels.yml` também aceita `repository_dispatch`, com controle de horário e recibo por dia/turno para evitar duplicação.

## Configurar em cron-job.org

Crie duas tarefas diárias no fuso `America/Sao_Paulo`:

| Horário | event_type | Previsão |
| --- | --- | --- |
| 05:15 | `boletim_hoje` | Bira, hoje, publica às 06:00 |
| 17:15 | `boletim_amanha` | Bia, amanhã, publica às 18:00 |

Método: `POST`.
URL: `https://api.github.com/repos/pabloramoa-dev/o-tempo-sp/dispatches`.
Headers: `Accept: application/vnd.github+json`, `Content-Type: application/json`, `Authorization: Bearer SEU_TOKEN`, `X-GitHub-Api-Version: 2022-11-28`.
Body JSON: `{"event_type":"boletim_hoje"}` ou `{"event_type":"boletim_amanha"}`.

Use token fine-grained do GitHub restrito a este repositório, com permissão Contents: Read and write. Não registre o token no GitHub, README ou logs. Resposta esperada HTTP 204.

Os cron internos continuam como reserva. A execução confere horário, dados reais, conta de destino e recibos antes de publicar; disparos atrasados fora da janela são ignorados.

**Situação:** a conexão do cron-job.org precisa ser feita pelo titular da conta; este arquivo não cria tarefas externas.
