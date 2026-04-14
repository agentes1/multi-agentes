RAGFlow Installation Guide

Requirements
WSL2 (Ubuntu recommended)
Docker installed in WSL


Installation Steps

1. Clone the repository
git clone https://github.com/infiniflow/ragflow.git
cd ragflow/docker

2. Start RAGFlow
sudo docker compose up -d

3. Fix Docker permissions (if needed)
If you get a permission error:

sudo usermod -aG docker $USER

Restart WSL:

wsl --shutdown

4. Verify containers
docker ps

Expected containers:

docker-ragflow-cpu-1
docker-es01-1
docker-minio-1
docker-mysql-1
docker-redis-1

5. Access RAGFlow
Open in your browser:

http://localhost

or:

http://localhost:9380
