# Phase 1: Backend Foundation Instructions

## 1. Virtual Environment Setup

Before writing any code, we need an isolated Python environment to manage our dependencies without affecting the global system Python installation. 

Since you are on Windows, follow these exact steps in your terminal or command prompt:

### Step A: Open your terminal inside your project folder
Navigate to `c:\Users\forwa\Desktop\Multi factor authentication\`

### Step B: Create the Virtual Environment
Run the following command to create a virtual environment named `venv`:
```powershell
python -m venv venv
```

### Step C: Activate the Virtual Environment
To activate the environment, run:
```powershell
.\venv\Scripts\activate
```
*(Note: If you encounter an execution policy error in PowerShell, run `Set-ExecutionPolicy Unrestricted -Scope CurrentUser` first, then try activating again.)*

After activation, your command prompt should be prefixed with `(venv)`.

---

## What this does:
This sets up an isolated container. Any packages we install (like FastAPI or SQLAlchemy) will only be installed inside this `venv` folder, ensuring our project remains clean, portable, and reproducible.
