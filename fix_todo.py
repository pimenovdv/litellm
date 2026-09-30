with open("todo.md", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "- [x] Вырезать лишний функционал из ядра системы (RAG, Guardrails, сторонние менеджеры секретов, телеметрию)." in line:
        lines[i] = line.replace("[x]", "[ ]")

with open("todo.md", "w") as f:
    f.writelines(lines)
