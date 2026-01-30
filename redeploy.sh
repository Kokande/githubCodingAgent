#!/bin/bash
git pull --all
docker-compose down
docker-compose up -d --build