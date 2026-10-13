/**
 * HTTP boundary reserved for the V2 ApplicationService.
 *
 * The UI must never contain governance rules. When the local API is introduced,
 * replace these placeholders with calls to the backend while keeping the UI
 * components independent of Python implementation details.
 */

export async function getHealth(baseUrl = "/api") {
  const response = await fetch(baseUrl + "/health");
  if (!response.ok) throw new Error("Unable to read application health");
  return response.json();
}

export async function startGovernanceRun(operation, payload, baseUrl = "/api") {
  const response = await fetch(baseUrl + "/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operation, payload })
  });
  if (!response.ok) throw new Error("Unable to start governance run");
  return response.json();
}
