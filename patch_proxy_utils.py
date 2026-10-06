import os

filepath = "Backend/litellm/proxy/utils.py"
with open(filepath, "r") as f:
    content = f.read()

bad_string = "callback_response = await callback.async_post_call_success_hook("
good_string = """if not hasattr(callback, 'async_post_call_success_hook'): continue
                callback_response = await callback.async_post_call_success_hook("""

if bad_string in content:
    content = content.replace(bad_string, good_string)

with open(filepath, "w") as f:
    f.write(content)
