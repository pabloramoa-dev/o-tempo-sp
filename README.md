# O TEMPO SP — @otemposp

Boletins com Bira e Bia cobrindo oito setores e 32 subprefeituras. Os Reels têm horário-alvo de 6h e 18h em São Paulo. O vídeo da manhã também sai como Story após a publicação do Reel. O GitHub inicia o preparo antes do horário-alvo. Atrasos do agendador podem atrasar a entrega.

A previsão de produção usa MET Norway Locationforecast, com atribuição na legenda e volume de chuva em milímetros. O vídeo vai diretamente à Meta. O registro separado por edição e formato em data/instagram permite retomar o Story sem reenviar o Reel. A publicação exige as credenciais da conta @otemposp. Execuções manuais iniciam em modo de teste por padrão.

## Boletim em dupla — Bira e Bia (padrão desde 18/11/2026)

Todo Reel (06h e 18h) sai com os **dois personagens conversando**, gerado por
`hyperframes/gerar_dupla.py` a partir da mesma pauta de produção:

- **06h (hoje):** Bira apresenta e a Bia acompanha. **18h (amanhã):** Bia
  apresenta e o Bira acompanha.
- As falas se alternam entre os dois: uma localidade falada por região e
  todas as 11 escritas no quadro. O CTA fica com quem apresenta e quem
  acompanha se despede.
- Quem fala ganha destaque e gesticula; o outro olha para ele. A legenda
  karaokê usa a cor de cada personagem.
- **Áudio:** voz + trilha CC0 com ducking (a música abaixa quando alguém
  fala) + efeitos do SFX Kit, normalizados a -14 LUFS.
- **Recursos gratuitos** versionados em `hyperframes/assets/dupla/`:
  SFX Kit (github.com/wyzowl/sfx-kit, CC0), "Sunset on the Beach" de Komiku
  (CC0, acervo SoundSafari/CC0-1.0-Music), figurantes Open Peeps (Pablo
  Stanley, CC0, via DiceBear) e fundo geopattern (MIT).
- **Reversão sem editar código:** variável de Actions `SP_FORMATO=solo`
  volta ao boletim de um personagem só.
- Teste visual com dados ilustrativos (nunca publicar):
  `python hyperframes/gerar_dupla.py --ilustrativo amanhã --out output/teste.mp4`

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



## Vozes de Bira e Bia — mesmos presets do Previsão RJ

O gerador de áudio do @otemposp utiliza Kokoro ONNX v1.0, com a mesma
função de combinação ponderada de estilos usada no @previsaorj.
Os presets abaixo foram conferidos em
`previsao-rj/src/previsao_rj/render/characters/pipeline.py` e aplicados em
`hyperframes/gerar_hf.py`:

| Personagem | Mistura de voz | Velocidade | Pausa entre falas |
| --- | --- | --- | --- |
| Bira | `pm_alex:0.82+pm_santa:0.18` | 1.04 | 0.22 s |
| Bia | `pf_dora:0.85+af_heart:0.15` | 1.02 | 0.24 s |

O filtro de narração também é o mesmo:
`highpass=f=80,acompressor=threshold=-18dB:ratio=2:attack=8:release=180,volume=1.1`.

O arquivo `src/otemposp/characters/kokoro.py` interpreta a mistura com
`get_voice_style` do Kokoro e aplica a mesma proporção de estilos antes da
síntese. Os testes `tests/test_vozes_iguais_rj.py` travam esses parâmetros
contra alterações involuntárias. Esta configuração reproduz os parâmetros de
voz do RJ; o resultado audível ainda depende do texto, versão dos modelos e
execução do render.

A trilha e os ruídos de transição do SP continuam mudos por decisão editorial
anterior; somente a voz do apresentador fica audível.


## Plantão diário de tempo severo — 14h de Brasília

Workflow: `.github/workflows/alerta_14h.yml`. A consulta é agendada diariamente para 17:00 UTC (14:00 BRT), com testes e checagem de 10 localidades reais do canal. Não confunda a hora do disparo com a hora prevista para a tempestade.

Fontes: INMET (aviso CAP válido com emissor oficial, status, município/UF, validade e URL verificados), consulta contextual à Defesa Civil, ICON Seamless e GFS Seamless via Open-Meteo. O monitor compara os dois modelos em janelas de 24 horas, bloqueia dados incompletos e trata aviso oficial não confirmado pelos dois modelos como **aviso do INMET**, jamais como concordância numérica.

Limites do plantão: precipitação de 20 mm/h, 30 mm/3h, 50 mm/24h; rajadas de 60 km/h ou mais; temporal WMO 95/96/99; granizo somente WMO 96/99 ou aviso oficial. O risco **não é ocorrência certa**. Com fonte INMET indisponível ou consulta vencida, não há publicação.

Se houver risco corroborado, ou aviso oficial válido para a área consultada, o workflow pode renderizar um Reel com o estúdio e as vozes originais do próprio canal e encaminhar Reel e Story à Meta, com recibos separados para não duplicar. Sem risco ou com validação incompleta, não publica. Para verificar manualmente sem postar, use **Run workflow** com `dry_run=true` (padrão); `dry_run=false` autoriza o mesmo fluxo de publicação, somente quando a validação tiver aprovado o alerta. Alterações no GitHub fazem apenas consulta e não publicam.

Relatórios, recibos e MP4 de cada execução ficam no artifact da execução por 3 dias. O histórico de publicações confirmadas fica em `data/alertas_14h_publicados.json`.
