#!/bin/bash
docker-compose up -d
echo "✅ Push Service started!"
echo "To run manually: docker exec -it push-service python main.py run all"
