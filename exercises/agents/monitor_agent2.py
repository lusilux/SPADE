import logging
import asyncio
from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour, FSMBehaviour, State
from spade.message import Message
import docker_utils

#logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)

#estados de la FSM
STATE_SCAN = "SCAN"
STATE_ALERT = "ALERT"
STATE_IDLE = "IDLE"


class MonitorBehaviour(PeriodicBehaviour):
    """
    Comportamiento periódico que lista todos los contenedores Docker activos.
    """
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


class MonitorFSM(FSMBehaviour):
    async def on_start(self):
        self.agent.logger.info(f"FSM starting at {self.current_state}")

    async def on_end(self):
        self.agent.logger.info(f"FSM finished at {self.current_state}")


class StateScan(State):
    async def run(self):
        self.agent.logger.info("FSM: Scanning Docker images...")
        containers = docker_utils.list_running_containers()
        suspicious = []

        suspicious_keywords = ["suspicious", "unknown", "malware"]

        for c in containers:
            if any(word in c["image"].lower() for word in suspicious_keywords):
                suspicious.append(c)

        # Guardamos en el agente lo detectado
        self.agent.suspicious = suspicious

        if suspicious:
            self.agent.logger.warning(f"Suspicious images found: {[c['image'] for c in suspicious]}")
            self.set_next_state(STATE_ALERT)
        else:
            self.agent.logger.info("No suspicious images detected.")
            self.set_next_state(STATE_IDLE)


class StateAlert(State):
    async def run(self):
        self.agent.logger.info("FSM: Reporting suspicious activity...")

        if hasattr(self.agent, "suspicious") and self.agent.suspicious:
            msg = Message(to="defender@localhost")  # JID del agente defensor
            msg.set_metadata("performative", "inform")
            msg.body = f"Suspicious images detected: {[c['image'] for c in self.agent.suspicious]}"

            await self.send(msg)
            self.agent.logger.info("Alert sent to defender.")
        else:
            self.agent.logger.info("No suspicious containers to report.")

        self.set_next_state(STATE_IDLE)


class StateIdle(State):
    async def run(self):
        self.agent.logger.info("FSM: Idle... waiting for next scan.")
        await asyncio.sleep(3)  #tiempo de espera antes de volver a escanear
        self.set_next_state(STATE_SCAN)


class MonitorAgent(Agent):
    async def setup(self):
        #logger
        self.logger = logging.getLogger(str(self.jid))
        self.logger.setLevel(logging.INFO)

        self.logger.info("MonitorAgent starting...")

        #periódico
        b = MonitorBehaviour(period=5)
        self.add_behaviour(b)

        #FSM
        fsm = MonitorFSM()
        fsm.add_state(name=STATE_SCAN, state=StateScan(), initial=True)
        fsm.add_state(name=STATE_ALERT, state=StateAlert())
        fsm.add_state(name=STATE_IDLE, state=StateIdle())
        fsm.add_transition(source=STATE_SCAN, dest=STATE_ALERT)
        fsm.add_transition(source=STATE_SCAN, dest=STATE_IDLE)
        fsm.add_transition(source=STATE_ALERT, dest=STATE_IDLE)
        fsm.add_transition(source=STATE_IDLE, dest=STATE_SCAN)

        self.add_behaviour(fsm)
