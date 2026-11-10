import { teamListCall, Organization } from "../networking";

export const fetchTeams = async (
  accessToken: string,
  userID: string | null,
  userRole: string | null,
  currentOrg: Organization | null,
  setTeams: (teams: Record<string, unknown>[]) => void,
) => {
  let givenTeams;
  if (userRole != "Admin" && userRole != "Admin Viewer") {
    givenTeams = await teamListCall(accessToken, currentOrg?.organization_id || null, userID);
  } else {
    givenTeams = await teamListCall(accessToken, currentOrg?.organization_id || null);
  }

  setTeams(givenTeams);
};
