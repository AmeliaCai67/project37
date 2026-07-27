<p align="center">
  <a href="./README.md">简体中文</a> |
  <a href="./README.en.md">English</a> |
  <a href="./README.ja.md">日本語</a>
</p>

---

# Wenshu · Project 37
> “All is number; its law endures.” — **37**

![](assets/maxresdefault.jpg)

## What is 37
**Project 37** is a **personal AI data analyst**, made for you.

I built this project so AI could free you from the suffering of being trapped inside the mess—and endow you instead with **the wisdom of standing outside it**.

Once, to draw insight from oceans of data, you had to face labyrinthine SQL, opaque analytical theory, or heavy, costly enterprise platforms. You were forced to *live inside* the chaos of details. Along the way, data often brought not answers, but pain.

**37 came into being to put an end to this suffering.**

- **Break down technical barriers**: She exists to lower the threshold. You need neither master complex data governance, nor write a single line of code.
- **Radically lightweight**: Unlike cumbersome enterprise tools, 37 is feather-light.
- **To toss them in is enough**: Papers, Excel sheets, Markdown notes—throw them all into a folder.

What remains—the deduction, the analysis, the verification; all the toil and ache that belong to Number—leave entirely to 37. Behind a vintage CRT screen, she filters out the noise and lays only the purest **wisdom of standing outside** upon your desk.

## Features
- **Truthseek (ReAct Agent)** — She is no mere Q&A machine. Given a hard task, she enters the loop of `Thought → Action → Observation`. Think first, act next, observe last—until the final answer is derived.

- **The Cabinet (File Knowledge)** — Upload Excel, PDF, CSV, or documents. She treats each file as a *fragment of knowledge*, retrieves with precision under your command, and unearths the meaning hidden behind the digits.

- **Numeracy (Auto Analysis)** — Complex statistics? She *derives* Python on the spot and runs it inside a sealed sandbox—speaking in data-facts, never hollow conjecture.

- **The Phosphor Screen (CRT Terminal)** — Every act of thought unfolds on a retro, skeuomorphic CRT. Phosphor-green monochrome light, old-TV power-off transitions—so the pulse of computation wears the weight of the physical.

- **Safeguard (Sandbox)** — Her sense of safety is unforgiving. All code runs under dual guard: AST static analysis and subprocess isolation. Her authority is yours to hold; she never overreaches into your privacy.

## Download

1. Visit [Releases](../../releases) and get the build for your OS.
2. **Windows**: Unzip `Project37-Windows.zip`, double-click `Project37.exe`.
3. **macOS**: Unzip `Project37-Mac.zip`, drag `Project37.app` into Applications, open via right-click.
4. On first launch, enter your DeepSeek API Key, and begin.

> If the system warns that the developer cannot be verified, or SmartScreen appears, choose “Run anyway” or “Right-click → Open”.

## Preview
### Home

![](assets/Pasted%20Graphic%2010.png)

### Reasoning

![](assets/Pasted%20Graphic%2012.png)
### Conclusion

![](assets/Pasted%20Graphic%2011.png)

### The Cabinet

![](assets/Pasted%20image%2020260505163334.png)

## Quick Start
### 1. Wake the environment

Bash

```
cd backend && cp .env.example .env
# Place your API Key in .env — open the gate to truth
```

### 2. Light the screen (backend + frontend)

Bash

```
# Backend
pip3 install -r requirements.txt && python3 main.py

# Frontend
cd frontend && npm install && npm run dev
```

## Closing
“This number… is perfectly complete.”

**Project 37** is still evolving. She may dwell a few extra seconds when truth demands it—but she keeps striving to turn cold code into warm, deep insight.

May she sit upon your desk, and help you find the *beautiful truths* buried in the numbers.
