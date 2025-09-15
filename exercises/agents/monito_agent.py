import logging
from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour
import docker_utils

# Configuración global de logging para toda la app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)

class MonitorBehaviour(PeriodicBehaviour):
    async def run(self):
        containers = docker_utils.list_running_containers()
        if containers:
            self.agent.logger.info("=== Monitor Report ===")
            for c in containers:
                self.agent.logger.info(
                    f"{c['id']} | {c['name']} | {c['status']} | {c['image']}"
                )
        else:
            self.agent.logger.info("No containers found.")

class MonitorAgent(Agent):
    async def setup(self):
        # logger vinculado al agente
        self.logger = logging.getLogger(str(self.jid))
        self.logger.setLevel(logging.INFO)

        self.logger.info("MonitorAgent starting...")

        # cada 5 segundos
        b = MonitorBehaviour(period=5)
        self.add_behaviour(b)
