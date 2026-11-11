# O TEMPO SP — @otemposp

Boletins com Bira e Bia cobrindo oito setores e 32 subprefeituras. Os Reels têm horário-alvo de 6h e 18h em São Paulo. O vídeo da manhã também sai como Story após a publicação do Reel. O GitHub inicia o preparo antes do horário-alvo. Atrasos do agendador podem atrasar a entrega.

A previsão de produção usa MET Norway Locationforecast, com atribuição na legenda e volume de chuva em milímetros. O vídeo vai diretamente à Meta. O registro separado por edição e formato em data/instagram permite retomar o Story sem reenviar o Reel. A publicação exige as credenciais da conta @otemposp. Execuções manuais iniciam em modo de teste por padrão.

## Rodízio editorial de localidades

O boletim diário usa **uma localidade por setor** (oito setores da capital e três do litoral), portanto são 11 pontos por Reel. O catálogo conta com **73 bairros e municípios** em `config/locais_sp.yaml`; ele é uma seleção editorial de pontos, não uma promessa de precisão para todos os bairros da cidade.

A função `daily_locations`, em `src/otemposp/geo.py`, seleciona os pontos de modo determinístico a partir da data local de publicação (`America/Sao_Paulo`) e do turno. **Bira (6h, hoje)** e **Bia (18h, amanhã)** usam pontos diferentes. A edição seguinte evita repetir o ponto anterior, e todos os pontos de cada setor recebem oportunidades de aparecer no ciclo. A previsão vem da MET Norway para a coordenada selecionada; **não é permitido trocar só o nome narrado mantendo a previsão de outro bairro**.

Em cada Reel, os nomes escolhidos devem aparecer individualmente no quadro e ser citados na fala da respectiva região. A capital cobre Norte (2 setores), Centro, Oeste, Leste (2 setores) e Sul (2 setores); o litoral cobre Norte, Baixada Santista e Sul. No Litoral Sul há três municípios no catálogo, de modo que a repetição será naturalmente mais frequente que em setores maiores. Os testes `tests/test_rodizio_diario.py` verificam cobertura, diversidade, distribuição equilibrada e correspondência entre nome narrado e mostrado.

