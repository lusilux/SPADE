import docker

client = docker.from_env()

def list_running_containers():
    containers = client.containers.list(all=True)
    info = []
    for c in containers:
        info.append({
            "id": c.id[:12],
            "name": c.name,
            "status": c.status,
            "image": c.image.tags[0] if c.image.tags else "unknown"
        })
    return info
