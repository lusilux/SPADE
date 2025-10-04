"""
NetworkDefenderAgent para SPADE

Este agente realiza
- Escaneo de puertos/servicios abiertos (host local y opcionalmente dockers)
- Mapea sockets a procesos para extraer ejecutable y PID
- Intenta obtener la versión del binario (--version, -v, -V)
- Busca configuraciones típicas para servicios conocidos
- Genera un informe JSON y lo envía al Monitor

Dependencias: spade, nmap, psutil, docker
Requiere privilegios para mapear procesos a sockets en muchos sistemas (ej. sudo)
"""
import asyncio
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import psutil
except Exception:
    psutil = None

try:
    import nmap
except Exception:
    nmap = None

try:
    import docker
except Exception:
    docker = None

from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message

# logging básico
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# FSM states
STATE_SCAN = "SCAN"
STATE_ANALYSE = "ANALYSE"
STATE_REPORT = "REPORT"
STATE_IDLE = "IDLE"

# timeouts
NM_SCAN_TIMEOUT = 60
VERSION_CHECK_TIMEOUT = 3


class StateScan(State):
    async def run(self):
        self.agent.logger.info("[SCAN] Inicio del escaneo de servicios locales (host).")
        report = {"host": {}, "containers": []}

		# 1) escaneo por sockets usando psutil
        host_services = []
        if psutil:
            try:
                # llamar en un thread para no bloquear el event loop
                # pide lista de conexiones de red abiertas que ve el SO
                conns = await asyncio.to_thread(lambda: psutil.net_connections(kind="inet"))
                for c in conns:
                    if not c.laddr:
                        continue
                    # Solo puertos listening
                    if c.status != psutil.CONN_LISTEN:
                        continue
                    laddr = c.laddr
                    pid = c.pid
                    proc_info = None
                    if pid:
                        try:
                            # creo objeto process para PID detectado
                            p = psutil.Process(pid)
                            # ruta completa a binario
                            # ejecutar p.exe() en thread por si es costoso
                            try:
                                exe = await asyncio.to_thread(p.exe) if hasattr(p, "exe") else None
                            except Exception:
                                exe = None
                            try:
                                name = await asyncio.to_thread(p.name)
                            except Exception:
                                name = None
                        except Exception:
	                        # si no se puede acceder al proceso
                            exe = None
                            name = None
                        proc_info = {"pid": pid, "name": name, "exe": exe}
                    host_services.append({
                        "ip": getattr(laddr, "ip", None),
                        "port": getattr(laddr, "port", None),
                        "proto": c.type.name if hasattr(c.type, "name") else str(getattr(c, "type", None)),
                        "process": proc_info,
                    })
            except Exception as e:
                self.agent.logger.warning(f"[SCAN] psutil error: {e}")
        else:
            self.agent.logger.warning("[SCAN] psutil no está disponible, saltando mapeo de procesos locales.")

        report["host"]["services"] = host_services

        # guardar informe parcial en el agente y pasar al siguiente estado
        self.agent.scan_report = report
        self.agent.logger.info("[SCAN] Escaneo completado; pasando a ANALYSE")
        self.set_next_state(STATE_ANALYSE)


class StateAnalyse(State):
    async def run(self):
        # Implementación mínima de prueba: simplemente registra y pasa a REPORT
        self.agent.logger.info("[ANALYSE] (prueba) Analizando informe...")
        # puedes ampliar con tu lógica real aquí
        self.set_next_state(STATE_REPORT)


class StateReport(State):
    async def run(self):
        self.agent.logger.info("[REPORT] (prueba) Generando informe y mostrando en consola")
        body = json.dumps(getattr(self.agent, "scan_report", {}), indent=2, default=str)
        # aquí mandar el mensaje XMPP al monitor; para la prueba solo loggeamos:
        self.agent.logger.info(f"[REPORT] Informe:\n{body}")
        # guardar localmente
        try:
            Path("/tmp/network_defender_report.json").write_text(body)
            self.agent.logger.info("[REPORT] Informe guardado en /tmp/network_defender_report.json")
        except Exception:
            pass
        # pasar a IDLE
        self.set_next_state(STATE_IDLE)


class StateIdle(State):
    async def run(self):
        self.agent.logger.info("[IDLE] Esperando 30 segundos antes del siguiente ciclo")
        await asyncio.sleep(30)
        self.set_next_state(STATE_SCAN)


class NetworkDefenderAgent(Agent):
    async def setup(self):
        self.logger = logging.getLogger(str(self.jid))
        self.logger.info("NetworkDefenderAgent starting...")

        fsm = FSMBehaviour()
        fsm.add_state(name=STATE_SCAN, state=StateScan(), initial=True)
        fsm.add_state(name=STATE_ANALYSE, state=StateAnalyse())
        fsm.add_state(name=STATE_REPORT, state=StateReport())
        fsm.add_state(name=STATE_IDLE, state=StateIdle())

        fsm.add_transition(source=STATE_SCAN, dest=STATE_ANALYSE)
        fsm.add_transition(source=STATE_ANALYSE, dest=STATE_REPORT)
        fsm.add_transition(source=STATE_REPORT, dest=STATE_IDLE)
        fsm.add_transition(source=STATE_IDLE, dest=STATE_SCAN)

        self.add_behaviour(fsm)


async def main():
    jid = "networkdefender@localhost"
    pwd = "password"

    agent = NetworkDefenderAgent(jid, pwd)

    # nota: start() puede ser coroutine o no
    start_maybe = agent.start()
    if asyncio.iscoroutine(start_maybe):
        await start_maybe
    else:
        try:
            await asyncio.wrap_future(start_maybe)
        except Exception:
            pass

    print("NetworkDefenderAgent running. Press Ctrl+C to stop.")
    try:
        while agent.is_alive():
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        print("KeyboardInterrupt received — stopping agent...")

    stop_maybe = agent.stop()
    if asyncio.iscoroutine(stop_maybe):
        await stop_maybe
    else:
        await asyncio.to_thread(lambda: stop_maybe or None)


if __name__ == "__main__":
    asyncio.run(main())
