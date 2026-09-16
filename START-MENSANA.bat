@echo off
REM This beginner-friendly launcher starts the complete local application.
where docker >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop was not found.
  echo Install it from https://www.docker.com/products/docker-desktop/ then run this file again.
  pause
  exit /b 1
)
start "" http://localhost:8000
docker compose up --build
pause
