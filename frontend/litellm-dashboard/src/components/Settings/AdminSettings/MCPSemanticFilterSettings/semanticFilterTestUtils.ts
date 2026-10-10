import NotificationManager from "@/components/molecules/notifications_manager";
import { testMCPSemanticFilter } from "@/components/networking";

/**
 * Represents the result of a semantic filter test.
 * @property {number} totalTools - The total number of tools available before filtering.
 * @property {number} selectedTools - The number of tools selected after filtering.
 * @property {string[]} tools - The names of the selected tools.
 */
export interface TestResult {
  totalTools: number;
  selectedTools: number;
  tools: string[];
}

/**
 * Represents the headers returned from the semantic filter test API.
 * @property {string | null} filter - The filter header string (e.g. "total->selected").
 * @property {string | null} tools - The tools header string containing comma-separated tool names.
 */
interface FilterHeaders {
  filter: string | null;
  tools: string | null;
}

/**
 * Parses the filter and tools headers from the API response.
 *
 * @param {FilterHeaders} headers - The headers containing the filter and tools information.
 * @returns {TestResult | null} The parsed test result or null if the filter header is missing.
 */
const parseFilterHeaders = (headers: FilterHeaders): TestResult | null => {
  if (!headers.filter) {
    return null;
  }

  const [total, selected] = headers.filter.split("->").map(Number);
  const tools = headers.tools ? headers.tools.split(",").map((name) => name.trim()) : [];

  return { totalTools: total, selectedTools: selected, tools };
};

/**
 * Executes a semantic filter test by calling the API and updating the state with the result or error.
 *
 * @param {Object} params - The parameters for the test execution.
 * @param {string} params.accessToken - The access token for API authentication.
 * @param {string} params.testModel - The model to use for testing.
 * @param {string} params.testQuery - The query string to test against the semantic filter.
 * @param {function(boolean): void} params.setIsTesting - State setter to indicate if testing is in progress.
 * @param {function(TestResult | null): void} params.setTestResult - State setter for the test result.
 * @param {function(string | null): void} params.setTestError - State setter for any errors encountered.
 * @returns {Promise<void>} A promise that resolves when the test completes.
 */
export const runSemanticFilterTest = async ({
  accessToken,
  testModel,
  testQuery,
  setIsTesting,
  setTestResult,
  setTestError,
}: {
  accessToken: string;
  testModel: string;
  testQuery: string;
  setIsTesting: (value: boolean) => void;
  setTestResult: (result: TestResult | null) => void;
  setTestError: (error: string | null) => void;
}) => {
  if (!testQuery || !testModel || !accessToken) {
    NotificationManager.error("Please enter a query and select a model");
    return;
  }

  setIsTesting(true);
  setTestResult(null);
  setTestError(null);

  try {
    const { headers } = await testMCPSemanticFilter(accessToken, testModel, testQuery);
    const parsedResult = parseFilterHeaders(headers);

    if (!parsedResult) {
      NotificationManager.warning("Semantic filter is not enabled or no tools were filtered");
      return;
    }

    setTestResult(parsedResult);
    NotificationManager.success("Semantic filter test completed successfully");
  } catch (error) {
    console.error("Test failed:", error);
    const message = error instanceof Error && error.message ? error.message : "Failed to test semantic filter";
    setTestError(message);
    NotificationManager.error("Failed to test semantic filter");
  } finally {
    setIsTesting(false);
  }
};

/**
 * Generates a equivalent cURL command for the semantic filter test.
 *
 * @param {string} testModel - The model name used in the test.
 * @param {string} testQuery - The user query for the test.
 * @returns {string} The cURL command string.
 */
export const getCurlCommand = (testModel: string, testQuery: string) =>
  `curl --location 'http://localhost:4000/v1/responses' \\
--header 'Content-Type: application/json' \\
--header 'Authorization: Bearer sk-1234' \\
--data '{
    "model": "${testModel}",
    "input": [
    {
      "role": "user",
      "content": "${testQuery || "Your query here"}",
      "type": "message"
    }
  ],
    "tools": [
        {
            "type": "mcp",
            "server_url": "litellm_proxy",
            "require_approval": "never"
        }
    ],
    "tool_choice": "required"
}'`;
