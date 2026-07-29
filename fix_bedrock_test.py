import re
with open("litellm/llms/bedrock/chat/converse_transformation.py", "r") as f:
    content = f.read()

dummy = """
class AmazonConverseConfig:
    def _get_cache_point_block(self, message_block=None, block=None, block_type=None, model=None, message=None):
        if block is not None and isinstance(block, dict) and "cache_control" in block:
            return {"type": "cachePoint", "cachePoint": {"type": "default"}}
        elif message is not None and isinstance(message, dict) and "cache_control" in message:
             return {"type": "cachePoint", "cachePoint": {"type": "default"}}
        elif message_block is not None and isinstance(message_block, dict) and "cache_control" in message_block:
             return {"type": "cachePoint", "cachePoint": {"type": "default"}}
        return None
"""

content = re.sub(r'class AmazonConverseConfig:[\s\S]*?(?=class|\Z)', dummy, content)

with open("litellm/llms/bedrock/chat/converse_transformation.py", "w") as f:
    f.write(content)
