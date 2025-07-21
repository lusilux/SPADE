import spade
import asyncio
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, CyclicBehaviour, OneShotBehaviour, State
from spade.message import Message

# offensiveAgent
# monitorAgent
# defensiveAgent

# attacker
STATE_ONE = "STATE_ONE"
STATE_TWO = "STATE_TWO"
STATE_THREE = "STATE_THREE"

class AttackBehaviour(FSMBehaviour):
    async def on_start(self):
        print(f"Attacker starting at initial state {self.current_state}")
         
    async def on_end(self):
        print(f"Attacker finished at state {self.current_state}")
        await self.agent.stop()

class StateOne(State):
    async def run(self):
        print("Attacker at state one of attack (preparing attack)")
        await asyncio.sleep(1)
        self.set_next_state(STATE_TWO)

class StateTwo(State):
    async def run(self):
        print("Attacker at state two of attack")
        await asyncio.sleep(1)
        msg = Message(to="monitor@localhost")
        msg.set_metadata("performative", "inform")
        msg.body = "DDOS attack"
                    
        await self.send(msg)
        print("Attacker Agent: Message sent!")
        await asyncio.sleep(1)
        self.set_next_state(STATE_THREE)

class StateThree(State):
    async def run(self):
        print("Attacker at state three of attack (final state)")
        await asyncio.sleep(1)

class offensiveAgent(Agent):
    async def setup(self):
        attack = AttackBehaviour()
        attack.add_state(name=STATE_ONE, state=StateOne(), initial=True)
        attack.add_state(name=STATE_TWO, state=StateTwo())
        attack.add_state(name=STATE_THREE, state=StateThree())
        attack.add_transition(source=STATE_ONE, dest=STATE_TWO)
        attack.add_transition(source=STATE_TWO, dest=STATE_THREE)
        self.add_behaviour(attack)
#end attacker
        
#monitor
class monitorAgent(Agent):
    class monitorBehaviour(CyclicBehaviour):
        async def on_start(self):
            print("Monitor starting to monitor...")
            
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg:
                print(f"Monitor Agent: Message received -> {msg.body}")
                await asyncio.sleep(1)
                if "attack" in msg.body:
                    print(f"Monitor Agent: alerting defender!")
                    await asyncio.sleep(1)
                    new_msg = Message(to="defender@localhost")
                    new_msg.set_metadata("performative", "inform")
                    new_msg.body = "Attack discovered"
                    
                    await self.send(new_msg)
                    print("Monitor Agent: Message sent!")

            
            
    async def setup(self):
        print("Monitor starting...")
        m = self.monitorBehaviour()
        self.add_behaviour(m)
#end monitor
        
#defender
class defenseBehaviour(OneShotBehaviour):
    async def run(self):
        print("Agente defensor listo")
        msg = await self.receive(timeout=10)
        if msg:
            await asyncio.sleep(1)
            print(f"AgenteDefensor: Respuesta activada por alerta: {msg.body}")
        else:
            print("AgenteDefensor: No se recibió alerta.")
        
class defenderAgent(Agent):
    async def setup(self):
        print("Defender starting...")
        defense = defenseBehaviour()
        self.add_behaviour(defense)
#end defender

async def main():
    monitor = monitorAgent("monitor@localhost", "monitor_passwd")
    defender = defenderAgent("defender@localhost", "defender_passwd")
    attacker = offensiveAgent("attacker@localhost", "attacker_passwd")
    
    await monitor.start(auto_register=True)
    await defender.start(auto_register=True)
    await attacker.start(auto_register=True)
    
    
    #await spade.wait_until_finished(attacker)
    #await spade.wait_until_finished(monitor)
    #await spade.wait_until_finished(defender)
    await asyncio.sleep(10)
    
    await monitor.stop()
    print("Monitor finished")
    await defender.stop()
    print("Defender finished")
    await attacker.stop()
    print("Attacker finished")

if __name__ == "__main__":
    spade.run(main())

