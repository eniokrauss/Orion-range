# Orion Range

[🇺🇸 English](README.md) | [🇧🇷 Português](README.pt-BR.md)

**Orion Range** é uma **plataforma open-source de orquestração de Cyber Range**, projetada para criar ambientes realistas de cibersegurança adversarial para **exercícios Red Team vs Blue Team**.

A plataforma permite que equipes de segurança projetem, implantem e operem ambientes complexos de treinamento cibernético, onde **ataques e defesas ocorrem em infraestruturas controladas e reproduzíveis**.

O Orion Range permite que **White Teams orquestrem ambientes corporativos completos**, incluindo sistemas vulneráveis, redes corporativas, infraestrutura defensiva e ecossistemas simulados de usuários.

---

# Por que Orion Range

Laboratórios tradicionais de segurança geralmente consistem em máquinas vulneráveis isoladas.

O Orion Range introduz um conceito diferente:

**orquestração de cyber ranges em escala corporativa.**

Em vez de máquinas isoladas, a plataforma modela:

- redes corporativas
- serviços internos
- infraestrutura defensiva
- endpoints de usuários
- dispositivos sem fio
- sistemas externos

Isso permite simulações adversariais realistas entre **Red Teams e Blue Teams**.

---

# Conceitos-chave

## Orquestração do White Team

O **White Team** controla todo o ambiente do exercício.

Eles podem:

- projetar topologias de rede
- inserir hosts e serviços
- adicionar vulnerabilidades
- definir cobertura MITRE ATT&CK
- configurar infraestrutura defensiva
- integrar ativos externos
- definir políticas do exercício
- implantar ou redefinir ambientes

---

## Operações de Red Team

O **Red Team executa operações ofensivas manuais**.

O Orion Range **não automatiza ataques**.

Os participantes do Red Team acessam o ambiente por meio de **VPN** e realizam:

- exploração de vulnerabilidades
- movimentação lateral
- escalonamento de privilégios
- persistência
- simulação de exfiltração de dados

---

## Operações de Blue Team

O **Blue Team monitora e defende o ambiente**.

A plataforma permite a implantação de infraestrutura defensiva, incluindo:

- SIEM
- EDR / XDR
- IDS / IPS
- monitoramento de rede
- telemetria de firewall
- registro de eventos de endpoints

Analistas do Blue Team investigam eventos e respondem a ataques em tempo real.

---

# Capacidades Principais

## Construtor de Cenários

Os White Teams podem criar ambientes definindo:

- topologia de rede
- hosts
- vulnerabilidades
- credenciais
- infraestrutura defensiva
- políticas de exercício
- técnicas do MITRE ATT&CK

---

## Biblioteca de Templates de Cenários

Os cenários podem ser salvos como **templates reutilizáveis**.

Isso permite:

- clonagem de cenários
- versionamento
- bibliotecas de cenários
- criação rápida de exercícios

---

## Designer Visual de Topologia

O Orion Range inclui um **construtor visual de topologias de rede**, permitindo que administradores projetem ambientes complexos, incluindo:

- redes internas
- segmentos DMZ
- redes Wi-Fi
- ambientes segmentados
- arquiteturas corporativas

---

## Ambientes Híbridos Ciber-Físicos

A plataforma suporta **integração com sistemas externos**.

Exemplos:

- dispositivos IoT
- protótipos eletrônicos
- equipamentos OT
- laboratórios remotos
- hardware físico de treinamento

Esses sistemas podem aparecer como **nós dentro da topologia do cenário**.

---

## Simulação de Ecossistema Corporativo

O Orion Range pode simular ambientes corporativos realistas, incluindo:

- estações de trabalho
- servidores
- endpoints de usuários
- dispositivos móveis
- dispositivos BYOD
- dispositivos de rede de convidados

Exemplos incluem:

- smartphones conectados ao Wi-Fi
- laptops pessoais
- tablets
- dispositivos não gerenciados

---

## Integração com MITRE ATT&CK

Os cenários podem ser mapeados para técnicas do **MITRE ATT&CK**.

Isso permite exercícios alinhados com o comportamento real de adversários, incluindo:

- Initial Access
- Execution
- Lateral Movement
- Credential Access
- Persistence
- Exfiltration

---

## Geração de Cenários Assistida por IA (Futuro)

Versões futuras do Orion Range suportarão **criação de cenários assistida por IA**.

Administradores poderão gerar ambientes usando **prompts em linguagem natural**.

Exemplo:

Criar uma rede corporativa com um servidor web na DMZ vulnerável a RCE, um ambiente interno com Active Directory, um servidor de banco de dados e um SIEM monitorando todos os endpoints.

O mecanismo de IA gera um **blueprint do cenário**, que pode então ser editado e implantado pelo White Team.

---

# Filosofia de Arquitetura

O Orion Range segue três princípios:

### Infraestrutura como Código

Todos os ambientes são definidos usando **blueprints de laboratório**.

### Ambientes Determinísticos

Cada ambiente pode ser **recriado e redefinido de forma consistente**.

### Realismo Operacional

A plataforma modela **ecossistemas corporativos completos**, em vez de máquinas isoladas.

---

# Status de Desenvolvimento

O Orion Range está atualmente em **desenvolvimento ativo**.

Funcionalidades planejadas incluem:

- motor completo de orquestração de cenários
- geração de blueprints assistida por IA
- suporte a cyber range multi-tenant
- modelagem avançada baseada em MITRE
- integrações corporativas

---

# Uso Pretendido

O Orion Range foi projetado para:

- treinamento em cibersegurança
- exercícios de Red Team
- treinamento de Blue Team
- simulações Purple Team
- pesquisa acadêmica
- desenvolvimento de capacidades de defesa cibernética

---

## Licença

O **Orion Range Core** é licenciado sob a **Apache License 2.0**.

Copyright (c) 2026 Kra2Sec.

Extensões corporativas e módulos avançados de orquestração são desenvolvidos separadamente pela Kra2Sec.

---

## Aviso Legal

O Orion Range é um projeto open-source independente desenvolvido pela Kra2Sec.

Ele não possui afiliação com nenhuma plataforma institucional de cyber range.

---

## Mantido por

Kra2Sec  
https://kra2sec.com

Fundador e Maintainer Principal: Ênio Krauss

---

## Visão

Nosso objetivo é fornecer uma base aberta e extensível para a construção de ambientes estruturados de simulação cibernética — preenchendo a lacuna entre laboratórios isolados e plataformas completas de cyber range operacional.

O Orion Range busca tornar o treinamento cibernético avançado **reproduzível, escalável e acessível**.
