import re

file_path = "Backend/litellm/proxy/common_utils/callback_utils.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r'\s*if "datadog_cost_management" in callback_specific_params and isinstance\(\s*callback_specific_params\["datadog_cost_management"\], dict\s*\):\s*init_params = callback_specific_params\["datadog_cost_management"\]\s*datadog_cost_management_obj = DatadogCostManagementLogger\(\*\*init_params\)\s*imported_list\.append\(datadog_cost_management_obj\)', '', content, flags=re.DOTALL)

with open(file_path, "w") as f:
    f.write(content)
