import asyncio
from monitor_agent import MonitorAgent

async def main():
    jid = "monitor2@localhost"
    passwd = "password"

    agent = MonitorAgent(jid, passwd)
    await agent.start()

    print("MonitorAgent running. Press Ctrl+C to stop.")
    while True:
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
