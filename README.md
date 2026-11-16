# O TEMPO SP — @otemposp

Boletins com Bira e Bia cobrindo oito setores e 32 subprefeituras. Os Reels têm horário-alvo de 6h e 18h em São Paulo. O vídeo da manhã também sai como Story após a publicação do Reel. O GitHub inicia o preparo antes do horário-alvo. Atrasos do agendador podem atrasar a entrega.

A previsão de produção usa MET Norway Locationforecast, com atribuição na legenda e volume de chuva em milímetros. O vídeo vai diretamente à Meta. O registro separado por edição e formato em data/instagram permite retomar o Story sem reenviar o Reel. A publicação exige as credenciais da conta @otemposp. Execuções manuais iniciam em modo de teste por padrão.

## Rodízio editorial de localidades

O boletim diário usa **uma localidade por setor** (oito setores da capital e três do litoral), portanto são 11 pontos por Reel. O catálogo conta com **73 bairros e municípios** em `config/locais_sp.yaml`; ele é uma seleção editorial de pontos, não uma promessa de precisão para todos os bairros da cidade.

A função `daily_locations`, em `src/otemposp/geo.py`, seleciona os pontos de modo determinístico a partir da data local de publicação (`America/Sao_Paulo`) e do turno. **Bira (6h, hoje)** e **Bia (18h, amanhã)** usam pontos diferentes. A edição seguinte evita repetir o ponto anterior, e todos os pontos de cada setor recebem oportunidades de aparecer no ciclo. A previsão vem da MET Norway para a coordenada selecionada; **não é permitido trocar só o nome narrado mantendo a previsão de outro bairro**.

Em cada Reel, os nomes escolhidos devem aparecer individualmente no quadro e ser citados na fala da respectiva região. A capital cobre Norte (2 setores), Centro, Oeste, Leste (2 setores) e Sul (2 setores); o litoral cobre Norte, Baixada Santista e Sul. No Litoral Sul há três municípios no catálogo, de modo que a repetição será naturalmente mais frequente que em setores maiores. Os testes `tests/test_rodizio_diario.py` verificam cobertura, diversidade, distribuição equilibrada e correspondência entre nome narrado e mostrado.


## Padrão editorial RJ adaptado para São Paulo (2026-11)

A edição mantém o estúdio **HyperFrames**, Bira (06h, hoje), Bia (18h,
amanhã), MET Norway e rodízio determinístico de 11 localidades em
oito setores da capital e três do litoral. O formato foi aproximado
da lógica do Previsão RJ sem importar dados, credenciais ou contas do Rio.

- **Abertura imediata:** primeira fala com localidade e maior máxima prevista
  do conjunto coletado, sem saudação ou apresentação genérica.
- **Roteiro enxuto:** uma fala sobre o destaque de cada uma das seis regiões;
  todas as 11 localidades e seus números permanecem no quadro.
- **Chuva:** somente o maior acumulado previsto, após os quadros, com valor
  em milímetros quando disponível; ausência de dado não vira 0 mm.
- **CTA:** uma única chamada de envio por Reel, no último trecho, relacionada
  ao destaque de chuva ou ao local de abertura.
- **Áudio:** voz em primeiro plano; trilha e whooshes desabilitados no
  compositor do Reel. O selo final identifica **SP**, sem mascote do Rio.
- **Consistência:** a legenda começa com a localidade em destaque. O arquivo
  `output/editorial.json` registra abertura, fonte, cobertura, chuva e CTA.
- **QA:** falha a renderização de produção quando faltar a abertura factual,
  qualquer das 11 localidades ou o CTA final único. Testes automáticos rodam
  antes do render e a publicação exige dados reais e recentes.
- **Segurança:** publicações automáticas preservadas nos horários existentes;
  não há mais publicação disparada por commit com mensagem especial. Para
  suspender o envio automático sem apagar workflows, configure a variável de
  Actions `SP_AUTOMATION_ENABLED=false`. Na ausência desta variável,
  os horários automáticos continuam funcionando. Execução manual permanece
  com `publicar=false` por padrão.

A versão paulista não deve afirmar que um bairro terá a maior chuva sem dado
próprio nem inferir crescimento de seguidores somente pela semelhança visual.
Para medir resultado são necessários insights reais de alcance, retenção,
compartilhamentos e seguidores por Reel, antes e depois das alterações.

