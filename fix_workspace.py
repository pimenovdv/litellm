import re

with open('Backend/pyproject.toml', 'r') as f:
    content = f.read()

content = re.sub(r'litellm-proxy-extras = .*', 'litellm-proxy-extras = { path = "../litellm-proxy-extras" }', content)
content = re.sub(r'litellm-enterprise = .*', 'litellm-enterprise = { path = "../enterprise" }', content)
content = content.replace('members = ["enterprise", "litellm-proxy-extras"]', 'members = []')

with open('Backend/pyproject.toml', 'w') as f:
    f.write(content)
